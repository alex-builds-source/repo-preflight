from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class CheckResult:
    id: str
    status: str  # pass | warn | fail
    message: str
    fix: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def _is_git_repo(path: Path) -> bool:
    proc = _run(["git", "rev-parse", "--is-inside-work-tree"], path)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _tracked_files(path: Path) -> list[str]:
    proc = _run(["git", "ls-files"], path)
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def check_readme(path: Path) -> CheckResult:
    if (path / "README.md").exists():
        return CheckResult("readme_present", "pass", "README.md present")
    return CheckResult(
        "readme_present",
        "fail",
        "README.md is missing",
        "Add a clear README with purpose, usage, and examples.",
    )


def check_license(path: Path) -> CheckResult:
    if (path / "LICENSE").exists() or (path / "LICENSE.md").exists():
        return CheckResult("license_present", "pass", "License file present")
    return CheckResult(
        "license_present",
        "warn",
        "No license file found",
        "Add LICENSE (e.g., MIT) so reuse terms are explicit.",
    )


def check_security(path: Path) -> CheckResult:
    if (path / "SECURITY.md").exists():
        return CheckResult("security_policy_present", "pass", "SECURITY.md present")
    return CheckResult(
        "security_policy_present",
        "warn",
        "SECURITY.md is missing",
        "Add SECURITY.md describing disclosure/reporting process.",
    )


def check_gitignore_secrets(path: Path) -> CheckResult:
    gitignore = path / ".gitignore"
    if not gitignore.exists():
        return CheckResult(
            "gitignore_basics",
            "fail",
            ".gitignore is missing",
            "Add .gitignore with secret and build artifact patterns.",
        )

    content = gitignore.read_text(encoding="utf-8")
    required = [".env", ".env.*", "!.env.example"]
    missing = [p for p in required if p not in content]
    if not missing:
        return CheckResult("gitignore_basics", "pass", "Secret-related .gitignore patterns present")

    return CheckResult(
        "gitignore_basics",
        "warn",
        f".gitignore missing patterns: {', '.join(missing)}",
        "Add missing env ignore patterns to reduce secret leaks.",
    )


def check_tracked_env(path: Path) -> CheckResult:
    if not _is_git_repo(path):
        return CheckResult(
            "tracked_env_files",
            "warn",
            "Not a git repository; skipped tracked .env check",
            "Initialize git and re-run checks.",
        )

    tracked = _tracked_files(path)
    env_files = [f for f in tracked if f == ".env" or (f.startswith(".env.") and f != ".env.example")]
    if not env_files:
        return CheckResult("tracked_env_files", "pass", "No tracked .env files found")

    return CheckResult(
        "tracked_env_files",
        "fail",
        f"Tracked env files detected: {', '.join(env_files)}",
        "Remove from git history/index and keep only placeholders like .env.example.",
    )


def check_tracked_keylike_files(path: Path) -> CheckResult:
    if not _is_git_repo(path):
        return CheckResult(
            "tracked_keylike_files",
            "warn",
            "Not a git repository; skipped tracked key-file check",
            "Initialize git and re-run checks.",
        )

    tracked = _tracked_files(path)
    risky_suffixes = (".pem", ".key", ".p12", ".pfx", ".kdbx")
    risky_names = {"id_rsa", "id_ed25519", "credentials.json"}

    risky = [f for f in tracked if f.endswith(risky_suffixes) or Path(f).name in risky_names]
    if not risky:
        return CheckResult("tracked_keylike_files", "pass", "No tracked key-like files found")

    return CheckResult(
        "tracked_keylike_files",
        "fail",
        f"Tracked key-like files detected: {', '.join(risky)}",
        "Remove keys/credentials from repo and rotate exposed secrets.",
    )


def check_gitleaks(path: Path) -> CheckResult:
    if not _is_git_repo(path):
        return CheckResult(
            "gitleaks_scan",
            "warn",
            "Not a git repository; skipped gitleaks scan",
            "Initialize git and re-run checks.",
        )

    if shutil.which("gitleaks") is None:
        return CheckResult(
            "gitleaks_scan",
            "warn",
            "gitleaks is not installed",
            "Install gitleaks and run: gitleaks git --redact",
        )

    proc = _run(["gitleaks", "git", "--redact", "--no-banner"], path)
    if proc.returncode == 0:
        return CheckResult("gitleaks_scan", "pass", "gitleaks scan passed")

    if proc.returncode == 1:
        return CheckResult(
            "gitleaks_scan",
            "fail",
            "gitleaks reported potential secret leaks",
            "Review findings, remove/rotate secrets, then re-run gitleaks.",
        )

    return CheckResult(
        "gitleaks_scan",
        "warn",
        "gitleaks did not complete successfully",
        "Run gitleaks manually to inspect configuration/runtime issues.",
    )


def run_checks(path: Path, *, include_gitleaks: bool = True) -> list[CheckResult]:
    results = [
        check_readme(path),
        check_license(path),
        check_security(path),
        check_gitignore_secrets(path),
        check_tracked_env(path),
        check_tracked_keylike_files(path),
    ]
    if include_gitleaks:
        results.append(check_gitleaks(path))
    return results
