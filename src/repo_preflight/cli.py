from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .checks import (
    DEFAULT_HISTORY_OBJECT_LIMIT,
    DEFAULT_MAX_HISTORY_BLOB_KIB,
    DEFAULT_MAX_TRACKED_FILE_KIB,
    CheckResult,
    available_check_ids,
    check_ids_for_profile,
    run_checks,
    validate_check_ids,
)
from .config import PreflightConfig, load_config
from .rulepacks import available_rule_packs, get_rule_pack


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


def _level_for_status(status: str) -> str:
    if status == "fail":
        return "error"
    if status == "warn":
        return "warning"
    return "note"


def resolve_runtime(
    args: argparse.Namespace,
    cfg: PreflightConfig,
) -> tuple[str, str | None, bool, bool, list[str], dict[str, str], int, int, int]:
    profile = args.profile or cfg.profile or "full"
    rule_pack_name = args.rule_pack or cfg.rule_pack

    defaults = profile_defaults(profile)

    strict = defaults["strict"]
    gitleaks_enabled = defaults["gitleaks"]

    check_ids = check_ids_for_profile(profile)
    severity_overrides: dict[str, str] = {}

    if rule_pack_name is not None:
        pack = get_rule_pack(rule_pack_name)
        if pack.strict is not None:
            strict = pack.strict

        for check_id in pack.include:
            if check_id not in check_ids:
                check_ids.append(check_id)

        if pack.exclude:
            excluded = set(pack.exclude)
            check_ids = [check_id for check_id in check_ids if check_id not in excluded]

        severity_overrides.update(pack.severity_overrides)

    if cfg.strict is not None:
        strict = cfg.strict
    if args.strict is not None:
        strict = args.strict

    if cfg.no_gitleaks is not None:
        gitleaks_enabled = not cfg.no_gitleaks
    if args.gitleaks is not None:
        gitleaks_enabled = args.gitleaks

    if cfg.include:
        for check_id in cfg.include:
            if check_id not in check_ids:
                check_ids.append(check_id)

    if cfg.exclude:
        excluded = set(cfg.exclude)
        check_ids = [check_id for check_id in check_ids if check_id not in excluded]

    max_tracked_file_kib = cfg.max_tracked_file_kib or DEFAULT_MAX_TRACKED_FILE_KIB
    if args.max_file_kib is not None:
        max_tracked_file_kib = args.max_file_kib

    max_history_blob_kib = cfg.max_history_blob_kib or DEFAULT_MAX_HISTORY_BLOB_KIB
    if args.max_history_kib is not None:
        max_history_blob_kib = args.max_history_kib

    history_object_limit = cfg.history_object_limit or DEFAULT_HISTORY_OBJECT_LIMIT
    if args.history_object_limit is not None:
        history_object_limit = args.history_object_limit

    if max_tracked_file_kib <= 0:
        raise ValueError("max tracked file size must be > 0 KiB")
    if max_history_blob_kib <= 0:
        raise ValueError("max history blob size must be > 0 KiB")
    if history_object_limit <= 0:
        raise ValueError("history object limit must be > 0")

    if not gitleaks_enabled:
        check_ids = [check_id for check_id in check_ids if check_id != "gitleaks_scan"]

    severity_overrides.update(cfg.severity_overrides)

    unknown = validate_check_ids(check_ids)
    if unknown:
        unknown_s = ", ".join(unknown)
        raise ValueError(f"Unknown check ids in resolved config: {unknown_s}")

    unknown_overrides = validate_check_ids(list(severity_overrides.keys()))
    if unknown_overrides:
        unknown_s = ", ".join(unknown_overrides)
        raise ValueError(f"Unknown check ids in severity_overrides: {unknown_s}")

    return (
        profile,
        rule_pack_name,
        strict,
        gitleaks_enabled,
        check_ids,
        severity_overrides,
        max_tracked_file_kib,
        max_history_blob_kib,
        history_object_limit,
    )


def print_human(
    path: Path,
    results: list[CheckResult],
    *,
    strict: bool,
    profile: str,
    rule_pack: str | None,
    check_ids: list[str],
    max_tracked_file_kib: int,
    max_history_blob_kib: int,
    history_object_limit: int,
) -> None:
    summary = summarize(results)
    code = exit_code(summary, strict=strict)
    overall = "FAIL" if code == 2 else ("WARN" if summary["warn"] else "PASS")
    print(
        f"repo-preflight: {overall} ({summary['fail']} fail, {summary['warn']} warn, {summary['pass']} pass)"
    )
    print(f"path: {path}")
    print(f"profile: {profile}")
    print(f"rule_pack: {rule_pack or 'none'}")
    print(f"mode: {'strict' if strict else 'default'}")
    print(f"max_tracked_file_kib: {max_tracked_file_kib}")
    print(f"max_history_blob_kib: {max_history_blob_kib}")
    print(f"history_object_limit: {history_object_limit}")
    print(f"checks: {', '.join(check_ids)}")

    for r in results:
        marker = r.status.upper()
        print(f"- [{marker}] {r.id}: {r.message}")
        if r.fix and r.status != "pass":
            print(f"  fix: {r.fix}")


def print_compact(path: Path, results: list[CheckResult], *, strict: bool, profile: str, rule_pack: str | None) -> None:
    summary = summarize(results)
    code = exit_code(summary, strict=strict)
    overall = "FAIL" if code == 2 else ("WARN" if summary["warn"] else "PASS")
    print(
        f"repo-preflight {overall} path={path} profile={profile} rule_pack={rule_pack or 'none'} fail={summary['fail']} warn={summary['warn']} pass={summary['pass']}"
    )

    for r in results:
        if r.status == "pass":
            continue
        fix = f" | fix={r.fix}" if r.fix else ""
        print(f"{r.status.upper()} {r.id}: {r.message}{fix}")


def build_payload(
    path: Path,
    results: list[CheckResult],
    *,
    strict: bool,
    profile: str,
    rule_pack: str | None,
    check_ids: list[str],
    config_path: str | None,
    max_tracked_file_kib: int,
    max_history_blob_kib: int,
    history_object_limit: int,
) -> dict:
    summary = summarize(results)
    return {
        "path": str(path),
        "profile": profile,
        "rule_pack": rule_pack,
        "strict": strict,
        "config_path": config_path,
        "max_tracked_file_kib": max_tracked_file_kib,
        "max_history_blob_kib": max_history_blob_kib,
        "history_object_limit": history_object_limit,
        "check_ids": check_ids,
        "summary": summary,
        "exit_code": exit_code(summary, strict=strict),
        "results": [r.to_dict() for r in results],
    }


def build_sarif_payload(
    path: Path,
    results: list[CheckResult],
    *,
    strict: bool,
    profile: str,
    rule_pack: str | None,
    check_ids: list[str],
    config_path: str | None,
) -> dict:
    summary = summarize(results)
    code = exit_code(summary, strict=strict)

    rules = [
        {
            "id": check_id,
            "name": check_id,
            "shortDescription": {"text": f"repo-preflight check: {check_id}"},
        }
        for check_id in check_ids
    ]

    sarif_results = []
    for r in results:
        if r.status == "pass":
            continue
        entry = {
            "ruleId": r.id,
            "level": _level_for_status(r.status),
            "message": {"text": r.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": str(path),
                        }
                    }
                }
            ],
            "properties": {
                "status": r.status,
            },
        }
        if r.fix:
            entry["properties"]["fix"] = r.fix
        sarif_results.append(entry)

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "repo-preflight",
                        "version": __version__,
                        "informationUri": "https://github.com/alex-builds-source/repo-preflight",
                        "rules": rules,
                    }
                },
                "results": sarif_results,
                "properties": {
                    "path": str(path),
                    "profile": profile,
                    "rule_pack": rule_pack,
                    "strict": strict,
                    "config_path": config_path,
                    "summary": summary,
                    "exit_code": code,
                },
            }
        ],
    }


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def cmd_check(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()
    if not target.exists() or not target.is_dir():
        print(f"Error: path is not a directory: {target}")
        return 2

    config_path = resolve_config_path(target, args.config, args.no_config)
    try:
        cfg = load_config(config_path) if config_path is not None else PreflightConfig()
        (
            profile,
            rule_pack,
            strict,
            _gitleaks_enabled,
            check_ids,
            severity_overrides,
            max_tracked_file_kib,
            max_history_blob_kib,
            history_object_limit,
        ) = resolve_runtime(args, cfg)
        results = run_checks(
            target,
            check_ids=check_ids,
            severity_overrides=severity_overrides,
            max_tracked_file_kib=max_tracked_file_kib,
            max_history_blob_kib=max_history_blob_kib,
            history_object_limit=history_object_limit,
        )
    except ValueError as err:
        print(f"Error: {err}")
        return 2

    config_path_str = str(config_path) if config_path and config_path.exists() else None
    payload = build_payload(
        target,
        results,
        strict=strict,
        profile=profile,
        rule_pack=rule_pack,
        check_ids=check_ids,
        config_path=config_path_str,
        max_tracked_file_kib=max_tracked_file_kib,
        max_history_blob_kib=max_history_blob_kib,
        history_object_limit=history_object_limit,
    )

    if args.sarif:
        print_json(
            build_sarif_payload(
                target,
                results,
                strict=strict,
                profile=profile,
                rule_pack=rule_pack,
                check_ids=check_ids,
                config_path=config_path_str,
            )
        )
    elif args.compact:
        print_compact(target, results, strict=strict, profile=profile, rule_pack=rule_pack)
    elif args.json:
        print_json(payload)
    else:
        print_human(
            target,
            results,
            strict=strict,
            profile=profile,
            rule_pack=rule_pack,
            check_ids=check_ids,
            max_tracked_file_kib=max_tracked_file_kib,
            max_history_blob_kib=max_history_blob_kib,
            history_object_limit=history_object_limit,
        )

    return exit_code(summarize(results), strict=strict)


def cmd_list_checks(_: argparse.Namespace) -> int:
    for check_id in available_check_ids():
        print(check_id)
    return 0


def cmd_list_rule_packs(_: argparse.Namespace) -> int:
    for name in available_rule_packs():
        pack = get_rule_pack(name)
        print(f"{name}: {pack.description}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repo-preflight", description="Repo publish-readiness and secret-safety checks")
    parser.add_argument("--version", action="version", version=f"repo-preflight {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Run repository checks")
    check.add_argument("--path", default=".", help="Repository path (default: current directory)")

    output_mode = check.add_mutually_exclusive_group()
    output_mode.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    output_mode.add_argument("--compact", action="store_true", help="Emit compact one-line issue output for CI logs")
    output_mode.add_argument("--sarif", action="store_true", help="Emit SARIF 2.1.0 output")

    check.add_argument("--profile", choices=["quick", "full", "ci"], help="Check profile")
    check.add_argument(
        "--rule-pack",
        choices=available_rule_packs(),
        help="Apply a rule pack for project-specific policy defaults",
    )
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
    check.add_argument(
        "--max-file-kib",
        type=int,
        help=f"Warn threshold for tracked large files in KiB (default: {DEFAULT_MAX_TRACKED_FILE_KIB})",
    )
    check.add_argument(
        "--max-history-kib",
        type=int,
        help=f"Warn threshold for history blob sizes in KiB (default: {DEFAULT_MAX_HISTORY_BLOB_KIB})",
    )
    check.add_argument(
        "--history-object-limit",
        type=int,
        help=f"Maximum git objects scanned in history mode (default: {DEFAULT_HISTORY_OBJECT_LIMIT})",
    )
    check.add_argument("--config", help="Path to config file (default: <path>/.repo-preflight.toml)")
    check.add_argument("--no-config", action="store_true", help="Ignore local config file")
    check.set_defaults(func=cmd_check)

    list_checks = sub.add_parser("list-checks", help="List available check ids")
    list_checks.set_defaults(func=cmd_list_checks)

    list_rule_packs = sub.add_parser("list-rule-packs", help="List available rule packs")
    list_rule_packs.set_defaults(func=cmd_list_rule_packs)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
