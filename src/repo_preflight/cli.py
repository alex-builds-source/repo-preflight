from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .checks import CheckResult, run_checks


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


def print_human(path: Path, results: list[CheckResult], *, strict: bool) -> None:
    summary = summarize(results)
    code = exit_code(summary, strict=strict)
    overall = "FAIL" if code == 2 else ("WARN" if summary["warn"] else "PASS")
    print(
        f"repo-preflight: {overall} ({summary['fail']} fail, {summary['warn']} warn, {summary['pass']} pass)"
    )
    print(f"path: {path}")
    print(f"mode: {'strict' if strict else 'default'}")

    for r in results:
        marker = r.status.upper()
        print(f"- [{marker}] {r.id}: {r.message}")
        if r.fix and r.status != "pass":
            print(f"  fix: {r.fix}")


def build_payload(path: Path, results: list[CheckResult], *, strict: bool) -> dict:
    summary = summarize(results)
    return {
        "path": str(path),
        "strict": strict,
        "summary": summary,
        "exit_code": exit_code(summary, strict=strict),
        "results": [r.to_dict() for r in results],
    }


def print_json(path: Path, results: list[CheckResult], *, strict: bool) -> None:
    print(json.dumps(build_payload(path, results, strict=strict), indent=2))


def cmd_check(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()
    if not target.exists() or not target.is_dir():
        print(f"Error: path is not a directory: {target}")
        return 2

    results = run_checks(target, include_gitleaks=not args.no_gitleaks)
    if args.json:
        print_json(target, results, strict=args.strict)
    else:
        print_human(target, results, strict=args.strict)

    return exit_code(summarize(results), strict=args.strict)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repo-preflight", description="Repo publish-readiness and secret-safety checks")
    parser.add_argument("--version", action="version", version=f"repo-preflight {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Run repository checks")
    check.add_argument("--path", default=".", help="Repository path (default: current directory)")
    check.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    check.add_argument("--strict", action="store_true", help="Treat warnings as failures for exit code")
    check.add_argument("--no-gitleaks", action="store_true", help="Skip gitleaks scan")
    check.set_defaults(func=cmd_check)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
