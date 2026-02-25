from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import __version__
from .checks import (
    DEFAULT_DIFF_TARGET,
    DEFAULT_HISTORY_OBJECT_LIMIT,
    DEFAULT_MAX_DIFF_CHANGED_LINES,
    DEFAULT_MAX_DIFF_FILES,
    DEFAULT_MAX_HISTORY_BLOB_KIB,
    DEFAULT_MAX_TRACKED_FILE_KIB,
    CheckResult,
    available_check_ids,
    check_ids_for_profile,
    run_checks,
    validate_check_ids,
)
from .config import PreflightConfig, load_config
from .rulepacks import RulePack, available_rule_packs, get_rule_pack

DEFAULT_PR_BASE_REF = "origin/main"


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


def _normalize_base_ref_for_remote(ref: str) -> str:
    if ref.startswith("origin/"):
        return ref
    if ref.startswith("refs/heads/"):
        branch = ref[len("refs/heads/"):]
        return f"origin/{branch}"
    return f"origin/{ref}"


def _resolve_pr_diff_base(explicit_base: str | None, pr_base_ref: str) -> str:
    if explicit_base:
        return explicit_base

    ci_base = os.getenv("GITHUB_BASE_REF") or os.getenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME")
    if ci_base:
        return _normalize_base_ref_for_remote(ci_base)

    return pr_base_ref


def _resolve_pr_diff_target(explicit_target: str | None) -> str:
    if explicit_target:
        return explicit_target

    ci_target = os.getenv("GITHUB_SHA") or os.getenv("CI_COMMIT_SHA")
    if ci_target:
        return ci_target

    return DEFAULT_DIFF_TARGET


def _level_for_status(status: str) -> str:
    if status == "fail":
        return "error"
    if status == "warn":
        return "warning"
    return "note"


def resolve_runtime(
    args: argparse.Namespace,
    cfg: PreflightConfig,
) -> tuple[
    str,
    str | None,
    bool,
    bool,
    list[str],
    dict[str, str],
    int,
    int,
    int,
    int,
    int,
    str,
    str,
    str | None,
    str,
]:
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

    max_diff_files = cfg.max_diff_files or DEFAULT_MAX_DIFF_FILES
    if args.max_diff_files is not None:
        max_diff_files = args.max_diff_files

    max_diff_changed_lines = cfg.max_diff_changed_lines or DEFAULT_MAX_DIFF_CHANGED_LINES
    if args.max_diff_changed_lines is not None:
        max_diff_changed_lines = args.max_diff_changed_lines

    diff_mode = args.diff_mode or cfg.diff_mode or "manual"
    pr_base_ref = args.pr_base_ref or cfg.pr_base_ref or DEFAULT_PR_BASE_REF

    explicit_base = args.diff_base if args.diff_base is not None else cfg.diff_base
    explicit_target = args.diff_target or cfg.diff_target

    if diff_mode == "pr":
        diff_base = _resolve_pr_diff_base(explicit_base, pr_base_ref)
        diff_target = _resolve_pr_diff_target(explicit_target)
    else:
        diff_base = explicit_base
        diff_target = explicit_target or DEFAULT_DIFF_TARGET

    if max_tracked_file_kib <= 0:
        raise ValueError("max tracked file size must be > 0 KiB")
    if max_history_blob_kib <= 0:
        raise ValueError("max history blob size must be > 0 KiB")
    if history_object_limit <= 0:
        raise ValueError("history object limit must be > 0")
    if max_diff_files <= 0:
        raise ValueError("max diff files must be > 0")
    if max_diff_changed_lines <= 0:
        raise ValueError("max diff changed lines must be > 0")

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
        max_diff_files,
        max_diff_changed_lines,
        diff_mode,
        pr_base_ref,
        diff_base,
        diff_target,
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
    max_diff_files: int,
    max_diff_changed_lines: int,
    diff_mode: str,
    pr_base_ref: str,
    diff_base: str | None,
    diff_target: str,
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
    print(f"diff_mode: {diff_mode}")
    if diff_mode == "pr":
        print(f"pr_base_ref: {pr_base_ref}")
    print(f"max_tracked_file_kib: {max_tracked_file_kib}")
    print(f"max_history_blob_kib: {max_history_blob_kib}")
    print(f"history_object_limit: {history_object_limit}")
    print(f"max_diff_files: {max_diff_files}")
    print(f"max_diff_changed_lines: {max_diff_changed_lines}")
    print(f"diff_base: {diff_base or 'none'}")
    print(f"diff_target: {diff_target}")
    print(f"checks: {', '.join(check_ids)}")

    for r in results:
        marker = r.status.upper()
        print(f"- [{marker}] {r.id}: {r.message}")
        if r.fix and r.status != "pass":
            print(f"  fix: {r.fix}")


def print_compact(
    path: Path,
    results: list[CheckResult],
    *,
    strict: bool,
    profile: str,
    rule_pack: str | None,
    diff_mode: str,
    diff_base: str | None,
    diff_target: str,
) -> None:
    summary = summarize(results)
    code = exit_code(summary, strict=strict)
    overall = "FAIL" if code == 2 else ("WARN" if summary["warn"] else "PASS")
    diff_repr = f"{diff_base}...{diff_target}" if diff_base else "none"
    print(
        f"repo-preflight {overall} path={path} profile={profile} rule_pack={rule_pack or 'none'} diff_mode={diff_mode} diff={diff_repr} fail={summary['fail']} warn={summary['warn']} pass={summary['pass']}"
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
    max_diff_files: int,
    max_diff_changed_lines: int,
    diff_mode: str,
    pr_base_ref: str,
    diff_base: str | None,
    diff_target: str,
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
        "max_diff_files": max_diff_files,
        "max_diff_changed_lines": max_diff_changed_lines,
        "diff_mode": diff_mode,
        "pr_base_ref": pr_base_ref,
        "diff_base": diff_base,
        "diff_target": diff_target,
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
    diff_mode: str,
    pr_base_ref: str,
    diff_base: str | None,
    diff_target: str,
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
                    "diff_mode": diff_mode,
                    "pr_base_ref": pr_base_ref,
                    "diff_base": diff_base,
                    "diff_target": diff_target,
                    "summary": summary,
                    "exit_code": code,
                },
            }
        ],
    }


def build_policy_doc(
    *,
    path: Path,
    profile: str,
    rule_pack: str | None,
    strict: bool,
    gitleaks_enabled: bool,
    diff_mode: str,
    pr_base_ref: str,
    diff_base: str | None,
    diff_target: str,
    max_tracked_file_kib: int,
    max_history_blob_kib: int,
    history_object_limit: int,
    max_diff_files: int,
    max_diff_changed_lines: int,
    check_ids: list[str],
    severity_overrides: dict[str, str],
    config_path: str | None,
) -> str:
    lines = [
        "# repo-preflight policy",
        "",
        f"- Path: `{path}`",
        f"- Profile: `{profile}`",
        f"- Rule pack: `{rule_pack or 'none'}`",
        f"- Strict mode: `{'on' if strict else 'off'}`",
        f"- Gitleaks check: `{'on' if gitleaks_enabled else 'off'}`",
        f"- Diff mode: `{diff_mode}`",
        f"- PR base ref fallback: `{pr_base_ref}`",
        f"- Diff refs: `{diff_base or 'none'}...{diff_target}`",
        f"- Max tracked file size: `{max_tracked_file_kib} KiB`",
        f"- Max history blob size: `{max_history_blob_kib} KiB`",
        f"- History object limit: `{history_object_limit}`",
        f"- Max diff files: `{max_diff_files}`",
        f"- Max diff changed lines: `{max_diff_changed_lines}`",
        f"- Config path: `{config_path or 'none'}`",
        "",
        "## Active checks",
    ]

    for check_id in check_ids:
        lines.append(f"- `{check_id}`")

    lines.extend(["", "## Severity overrides"])
    if not severity_overrides:
        lines.append("- _(none)_")
    else:
        for check_id, status in sorted(severity_overrides.items()):
            lines.append(f"- `{check_id}` -> `{status}`")

    return "\n".join(lines) + "\n"


def build_policy_template(*, rule_pack_name: str, profile: str, strict: bool | None = None) -> str:
    pack: RulePack = get_rule_pack(rule_pack_name)
    effective_strict = strict if strict is not None else (pack.strict if pack.strict is not None else profile_defaults(profile)["strict"])

    lines = [
        "# .repo-preflight.toml template",
        "",
        f"# Rule-pack-oriented template for: {rule_pack_name}",
        "",
        "[preflight]",
        f"profile = \"{profile}\"",
        f"rule_pack = \"{rule_pack_name}\"",
        f"strict = {'true' if effective_strict else 'false'}",
        "no_gitleaks = false",
        "diff_mode = \"pr\"",
        "pr_base_ref = \"origin/main\"",
        "diff_target = \"HEAD\"",
        "max_tracked_file_kib = 5120",
        "max_history_blob_kib = 5120",
        "history_object_limit = 20000",
        "max_diff_files = 200",
        "max_diff_changed_lines = 4000",
        "",
        "[checks]",
        "include = []",
        "exclude = []",
        "",
        "[severity_overrides]",
    ]

    if pack.severity_overrides:
        for check_id, status in sorted(pack.severity_overrides.items()):
            lines.append(f"{check_id} = \"{status}\"")
    else:
        lines.append("# (none)")

    return "\n".join(lines) + "\n"


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
            gitleaks_enabled,
            check_ids,
            severity_overrides,
            max_tracked_file_kib,
            max_history_blob_kib,
            history_object_limit,
            max_diff_files,
            max_diff_changed_lines,
            diff_mode,
            pr_base_ref,
            diff_base,
            diff_target,
        ) = resolve_runtime(args, cfg)
        results = run_checks(
            target,
            check_ids=check_ids,
            severity_overrides=severity_overrides,
            max_tracked_file_kib=max_tracked_file_kib,
            max_history_blob_kib=max_history_blob_kib,
            history_object_limit=history_object_limit,
            diff_base=diff_base,
            diff_target=diff_target,
            max_diff_files=max_diff_files,
            max_diff_changed_lines=max_diff_changed_lines,
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
        max_diff_files=max_diff_files,
        max_diff_changed_lines=max_diff_changed_lines,
        diff_mode=diff_mode,
        pr_base_ref=pr_base_ref,
        diff_base=diff_base,
        diff_target=diff_target,
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
                diff_mode=diff_mode,
                pr_base_ref=pr_base_ref,
                diff_base=diff_base,
                diff_target=diff_target,
            )
        )
    elif args.compact:
        print_compact(
            target,
            results,
            strict=strict,
            profile=profile,
            rule_pack=rule_pack,
            diff_mode=diff_mode,
            diff_base=diff_base,
            diff_target=diff_target,
        )
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
            max_diff_files=max_diff_files,
            max_diff_changed_lines=max_diff_changed_lines,
            diff_mode=diff_mode,
            pr_base_ref=pr_base_ref,
            diff_base=diff_base,
            diff_target=diff_target,
        )

    return exit_code(summarize(results), strict=strict)


def cmd_policy_doc(args: argparse.Namespace) -> int:
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
            gitleaks_enabled,
            check_ids,
            severity_overrides,
            max_tracked_file_kib,
            max_history_blob_kib,
            history_object_limit,
            max_diff_files,
            max_diff_changed_lines,
            diff_mode,
            pr_base_ref,
            diff_base,
            diff_target,
        ) = resolve_runtime(args, cfg)
    except ValueError as err:
        print(f"Error: {err}")
        return 2

    config_path_str = str(config_path) if config_path and config_path.exists() else None
    doc = build_policy_doc(
        path=target,
        profile=profile,
        rule_pack=rule_pack,
        strict=strict,
        gitleaks_enabled=gitleaks_enabled,
        diff_mode=diff_mode,
        pr_base_ref=pr_base_ref,
        diff_base=diff_base,
        diff_target=diff_target,
        max_tracked_file_kib=max_tracked_file_kib,
        max_history_blob_kib=max_history_blob_kib,
        history_object_limit=history_object_limit,
        max_diff_files=max_diff_files,
        max_diff_changed_lines=max_diff_changed_lines,
        check_ids=check_ids,
        severity_overrides=severity_overrides,
        config_path=config_path_str,
    )

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(doc, encoding="utf-8")
        print(f"Wrote policy doc: {output_path}")
    else:
        print(doc, end="")

    return 0


def cmd_policy_template(args: argparse.Namespace) -> int:
    template = build_policy_template(rule_pack_name=args.rule_pack, profile=args.profile, strict=args.strict)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(template, encoding="utf-8")
        print(f"Wrote policy template: {output_path}")
    else:
        print(template, end="")

    return 0


def cmd_list_checks(_: argparse.Namespace) -> int:
    for check_id in available_check_ids():
        print(check_id)
    return 0


def cmd_list_rule_packs(_: argparse.Namespace) -> int:
    for name in available_rule_packs():
        pack = get_rule_pack(name)
        print(f"{name}: {pack.description}")
    return 0


def _add_common_policy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", choices=["quick", "full", "ci"], help="Check profile")
    parser.add_argument(
        "--rule-pack",
        choices=available_rule_packs(),
        help="Apply a rule pack for project-specific policy defaults",
    )
    parser.add_argument(
        "--strict",
        dest="strict",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Treat warnings as failures for exit code",
    )
    parser.add_argument(
        "--gitleaks",
        dest="gitleaks",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable gitleaks check",
    )
    parser.add_argument(
        "--max-file-kib",
        type=int,
        help=f"Warn threshold for tracked large files in KiB (default: {DEFAULT_MAX_TRACKED_FILE_KIB})",
    )
    parser.add_argument(
        "--max-history-kib",
        type=int,
        help=f"Warn threshold for history blob sizes in KiB (default: {DEFAULT_MAX_HISTORY_BLOB_KIB})",
    )
    parser.add_argument(
        "--history-object-limit",
        type=int,
        help=f"Maximum git objects scanned in history mode (default: {DEFAULT_HISTORY_OBJECT_LIMIT})",
    )
    parser.add_argument(
        "--max-diff-files",
        type=int,
        help=f"Warn threshold for number of changed files in diff mode (default: {DEFAULT_MAX_DIFF_FILES})",
    )
    parser.add_argument(
        "--max-diff-changed-lines",
        type=int,
        help=f"Warn threshold for total changed lines in diff mode (default: {DEFAULT_MAX_DIFF_CHANGED_LINES})",
    )
    parser.add_argument(
        "--diff-mode",
        choices=["manual", "pr"],
        help="Diff resolution mode: manual refs or PR/CI-aware base selection",
    )
    parser.add_argument(
        "--pr-base-ref",
        help=f"Fallback remote base ref for PR mode (default: {DEFAULT_PR_BASE_REF})",
    )
    parser.add_argument("--diff-base", help="Base ref for diff-aware checks (e.g., origin/main)")
    parser.add_argument(
        "--diff-target",
        default=None,
        help=f"Target ref for diff-aware checks (default: {DEFAULT_DIFF_TARGET})",
    )
    parser.add_argument("--config", help="Path to config file (default: <path>/.repo-preflight.toml)")
    parser.add_argument("--no-config", action="store_true", help="Ignore local config file")


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

    _add_common_policy_args(check)
    check.set_defaults(func=cmd_check)

    policy_doc = sub.add_parser("policy-doc", help="Render effective policy as markdown")
    policy_doc.add_argument("--path", default=".", help="Repository path (default: current directory)")
    policy_doc.add_argument("--output", help="Write markdown output to a file")
    _add_common_policy_args(policy_doc)
    policy_doc.set_defaults(func=cmd_policy_doc)

    policy_template = sub.add_parser("policy-template", help="Render rule-pack policy template as .toml")
    policy_template.add_argument("--rule-pack", choices=available_rule_packs(), required=True, help="Rule pack name")
    policy_template.add_argument("--profile", choices=["quick", "full", "ci"], default="ci", help="Baseline profile")
    policy_template.add_argument(
        "--strict",
        dest="strict",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override strict mode in template",
    )
    policy_template.add_argument("--output", help="Write template output to a file")
    policy_template.set_defaults(func=cmd_policy_template)

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
