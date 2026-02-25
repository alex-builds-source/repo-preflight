from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .checks import (
    CheckResult,
    available_check_ids,
    check_ids_for_profile,
    run_checks,
    validate_check_ids,
)
from .config import PreflightConfig, load_config


def summarize(results: list[CheckResult]) -> dict[str, int]:
    out = {"pass": 0, "warn": 0, "fail": 0}
    for r in results:
        out[r.status] += 1
    return out


def exit_code(summary: dict[str, int], *, strict: bool = False) -> int:
    if summary["fail"] > 0:
        return 2
    if summary["warn"] > 0:
        return 2 if strict else 1
    return 0


def profile_defaults(profile: str) -> dict[str, bool]:
    if profile == "ci":
        return {"strict": True, "gitleaks": True}
    if profile == "quick":
        return {"strict": False, "gitleaks": False}
    return {"strict": False, "gitleaks": True}


def resolve_config_path(target: Path, explicit_config: str | None, no_config: bool) -> Path | None:
    if no_config:
        return None
    if explicit_config:
        return Path(explicit_config).expanduser().resolve()
    return target / ".repo-preflight.toml"


def resolve_runtime(
    args: argparse.Namespace,
    cfg: PreflightConfig,
) -> tuple[str, bool, bool, list[str], dict[str, str]]:
    profile = args.profile or cfg.profile or "full"

    defaults = profile_defaults(profile)

    strict = defaults["strict"]
    if cfg.strict is not None:
        strict = cfg.strict
    if args.strict is not None:
        strict = args.strict

    gitleaks_enabled = defaults["gitleaks"]
    if cfg.no_gitleaks is not None:
        gitleaks_enabled = not cfg.no_gitleaks
    if args.gitleaks is not None:
        gitleaks_enabled = args.gitleaks

    check_ids = check_ids_for_profile(profile)

    if cfg.include:
        for check_id in cfg.include:
            if check_id not in check_ids:
                check_ids.append(check_id)

    if cfg.exclude:
        excluded = set(cfg.exclude)
        check_ids = [check_id for check_id in check_ids if check_id not in excluded]

    if not gitleaks_enabled:
        check_ids = [check_id for check_id in check_ids if check_id != "gitleaks_scan"]

    unknown = validate_check_ids(check_ids)
    if unknown:
        unknown_s = ", ".join(unknown)
        raise ValueError(f"Unknown check ids in resolved config: {unknown_s}")

    if validate_check_ids(list(cfg.severity_overrides.keys())):
        unknown_overrides = ", ".join(validate_check_ids(list(cfg.severity_overrides.keys())))
        raise ValueError(f"Unknown check ids in severity_overrides: {unknown_overrides}")

    return profile, strict, gitleaks_enabled, check_ids, cfg.severity_overrides


def print_human(path: Path, results: list[CheckResult], *, strict: bool, profile: str, check_ids: list[str]) -> None:
    summary = summarize(results)
    code = exit_code(summary, strict=strict)
    overall = "FAIL" if code == 2 else ("WARN" if summary["warn"] else "PASS")
    print(
        f"repo-preflight: {overall} ({summary['fail']} fail, {summary['warn']} warn, {summary['pass']} pass)"
    )
    print(f"path: {path}")
    print(f"profile: {profile}")
    print(f"mode: {'strict' if strict else 'default'}")
    print(f"checks: {', '.join(check_ids)}")

    for r in results:
        marker = r.status.upper()
        print(f"- [{marker}] {r.id}: {r.message}")
        if r.fix and r.status != "pass":
            print(f"  fix: {r.fix}")


def build_payload(
    path: Path,
    results: list[CheckResult],
    *,
    strict: bool,
    profile: str,
    check_ids: list[str],
    config_path: str | None,
) -> dict:
    summary = summarize(results)
    return {
        "path": str(path),
        "profile": profile,
        "strict": strict,
        "config_path": config_path,
        "check_ids": check_ids,
        "summary": summary,
        "exit_code": exit_code(summary, strict=strict),
        "results": [r.to_dict() for r in results],
    }


def print_json(
    path: Path,
    results: list[CheckResult],
    *,
    strict: bool,
    profile: str,
    check_ids: list[str],
    config_path: str | None,
) -> None:
    print(
        json.dumps(
            build_payload(
                path,
                results,
                strict=strict,
                profile=profile,
                check_ids=check_ids,
                config_path=config_path,
            ),
            indent=2,
        )
    )


def cmd_check(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()
    if not target.exists() or not target.is_dir():
        print(f"Error: path is not a directory: {target}")
        return 2

    config_path = resolve_config_path(target, args.config, args.no_config)
    try:
        cfg = load_config(config_path) if config_path is not None else PreflightConfig()
        profile, strict, _gitleaks_enabled, check_ids, severity_overrides = resolve_runtime(args, cfg)
        results = run_checks(target, check_ids=check_ids, severity_overrides=severity_overrides)
    except ValueError as err:
        print(f"Error: {err}")
        return 2

    config_path_str = str(config_path) if config_path and config_path.exists() else None

    if args.json:
        print_json(
            target,
            results,
            strict=strict,
            profile=profile,
            check_ids=check_ids,
            config_path=config_path_str,
        )
    else:
        print_human(target, results, strict=strict, profile=profile, check_ids=check_ids)

    return exit_code(summarize(results), strict=strict)


def cmd_list_checks(_: argparse.Namespace) -> int:
    for check_id in available_check_ids():
        print(check_id)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repo-preflight", description="Repo publish-readiness and secret-safety checks")
    parser.add_argument("--version", action="version", version=f"repo-preflight {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Run repository checks")
    check.add_argument("--path", default=".", help="Repository path (default: current directory)")
    check.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    check.add_argument("--profile", choices=["quick", "full", "ci"], help="Check profile")
    check.add_argument(
        "--strict",
        dest="strict",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Treat warnings as failures for exit code",
    )
    check.add_argument(
        "--gitleaks",
        dest="gitleaks",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable gitleaks check",
    )
    check.add_argument("--config", help="Path to config file (default: <path>/.repo-preflight.toml)")
    check.add_argument("--no-config", action="store_true", help="Ignore local config file")
    check.set_defaults(func=cmd_check)

    list_checks = sub.add_parser("list-checks", help="List available check ids")
    list_checks.set_defaults(func=cmd_list_checks)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
