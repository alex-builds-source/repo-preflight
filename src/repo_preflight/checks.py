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


def check_git_repository(path: Path) -> CheckResult:
    if _is_git_repo(path):
        return CheckResult("git_repository", "pass", "Path is a git repository")

    return CheckResult(
        "git_repository",
        "fail",
        "Path is not a git repository",
        "Run 'git init' (or use an existing repo) before running publish checks.",
    )


def check_remote_origin(path: Path) -> CheckResult:
    if not _is_git_repo(path):
        return CheckResult(
            "remote_origin",
            "warn",
            "Not a git repository; skipped origin remote check",
            "Initialize git and configure an origin remote.",
        )

    proc = _run(["git", "remote", "get-url", "origin"], path)
    if proc.returncode != 0:
        return CheckResult(
            "remote_origin",
            "warn",
            "No 'origin' remote configured",
            "Add a publish target with: git remote add origin <url>",
        )

    url = proc.stdout.strip()
    return CheckResult("remote_origin", "pass", f"origin remote configured ({url})")


def check_clean_worktree(path: Path) -> CheckResult:
    if not _is_git_repo(path):
        return CheckResult(
            "clean_worktree",
            "warn",
            "Not a git repository; skipped worktree cleanliness check",
            "Initialize git and commit changes before publish checks.",
        )

    proc = _run(["git", "status", "--porcelain"], path)
    if proc.returncode != 0:
        return CheckResult(
            "clean_worktree",
            "warn",
            "Could not determine git worktree state",
            "Run 'git status' manually and resolve repository state.",
        )

    if proc.stdout.strip() == "":
        return CheckResult("clean_worktree", "pass", "Working tree is clean")

    return CheckResult(
        "clean_worktree",
        "warn",
        "Working tree has uncommitted changes",
        "Commit or stash pending changes before publishing.",
    )


def check_default_branch(path: Path) -> CheckResult:
    if not _is_git_repo(path):
        return CheckResult(
            "default_branch_style",
            "warn",
            "Not a git repository; skipped branch check",
            "Initialize git and align branch naming conventions.",
        )

    proc = _run(["git", "branch", "--show-current"], path)
    if proc.returncode != 0:
        return CheckResult(
            "default_branch_style",
            "warn",
            "Could not determine current branch",
            "Check branch naming manually (prefer main).",
        )

    branch = proc.stdout.strip()
    if branch in {"main", "master"}:
        return CheckResult("default_branch_style", "pass", f"Current branch '{branch}' is conventional")

    return CheckResult(
        "default_branch_style",
        "warn",
        f"Current branch is '{branch}'",
        "Consider using 'main' (or a documented branch policy) before public release.",
    )


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


def check_license_spdx(path: Path) -> CheckResult:
    license_file = path / "LICENSE"
    if not license_file.exists():
        license_file = path / "LICENSE.md"

    if not license_file.exists():
        return CheckResult(
            "license_identifier",
            "warn",
            "No license file found; skipped license identifier check",
            "Add a LICENSE file and include an SPDX identifier where practical.",
        )

    text = license_file.read_text(encoding="utf-8", errors="ignore")
    normalized = text.lower()

    if "spdx-license-identifier:" in normalized:
        return CheckResult("license_identifier", "pass", "SPDX identifier found in license file")

    known_markers = ["mit license", "apache license", "mozilla public license", "gnu general public license", "bsd"]
    if any(marker in normalized for marker in known_markers):
        return CheckResult(
            "license_identifier",
            "warn",
            "License text found but no explicit SPDX identifier",
            "Optional: add an SPDX identifier line for machine-readable license parsing.",
        )

    return CheckResult(
        "license_identifier",
        "warn",
        "Could not recognize license text format",
        "Verify license file contents and consider adding an SPDX identifier.",
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
        check_git_repository(path),
        check_remote_origin(path),
        check_clean_worktree(path),
        check_default_branch(path),
        check_readme(path),
        check_license(path),
        check_license_spdx(path),
        check_security(path),
        check_gitignore_secrets(path),
        check_tracked_env(path),
        check_tracked_keylike_files(path),
    ]
    if include_gitleaks:
        results.append(check_gitleaks(path))
    return results
