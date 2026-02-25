from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


VALID_STATUSES = {"pass", "warn", "fail"}
DEFAULT_MAX_TRACKED_FILE_KIB = 5120  # 5 MiB
DEFAULT_MAX_HISTORY_BLOB_KIB = 5120  # 5 MiB
DEFAULT_HISTORY_OBJECT_LIMIT = 20000


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


def check_tracked_large_files(path: Path, *, max_file_kib: int = DEFAULT_MAX_TRACKED_FILE_KIB) -> CheckResult:
    if not _is_git_repo(path):
        return CheckResult(
            "tracked_large_files",
            "warn",
            "Not a git repository; skipped tracked large-file check",
            "Initialize git and re-run checks.",
        )

    threshold_bytes = max_file_kib * 1024
    tracked = _tracked_files(path)
    oversized: list[tuple[str, int]] = []
    for rel in tracked:
        p = path / rel
        if not p.exists() or not p.is_file():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > threshold_bytes:
            oversized.append((rel, size))

    if not oversized:
        return CheckResult("tracked_large_files", "pass", f"No tracked files above {max_file_kib} KiB")

    oversized.sort(key=lambda x: x[1], reverse=True)
    preview = ", ".join(f"{name} ({size // 1024} KiB)" for name, size in oversized[:5])
    more = "" if len(oversized) <= 5 else f" (+{len(oversized) - 5} more)"
    return CheckResult(
        "tracked_large_files",
        "warn",
        f"Tracked files exceed {max_file_kib} KiB: {preview}{more}",
        "Use Git LFS or external artifact storage for large assets where appropriate.",
    )


def check_history_large_blobs(
    path: Path,
    *,
    max_blob_kib: int = DEFAULT_MAX_HISTORY_BLOB_KIB,
    object_limit: int = DEFAULT_HISTORY_OBJECT_LIMIT,
) -> CheckResult:
    if not _is_git_repo(path):
        return CheckResult(
            "history_large_blobs",
            "warn",
            "Not a git repository; skipped history large-blob check",
            "Initialize git and re-run checks.",
        )

    rev = _run(["git", "rev-list", "--objects", "--all"], path)
    if rev.returncode != 0:
        return CheckResult(
            "history_large_blobs",
            "warn",
            "Could not enumerate git history objects",
            "Run 'git rev-list --objects --all' manually to inspect history state.",
        )

    object_ids: list[str] = []
    first_path: dict[str, str] = {}
    for line in rev.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split(" ", 1)
        oid = parts[0].strip()
        if not oid:
            continue
        if oid not in first_path:
            object_ids.append(oid)
            if len(parts) == 2 and parts[1].strip():
                first_path[oid] = parts[1].strip()

    truncated = False
    if len(object_ids) > object_limit:
        object_ids = object_ids[:object_limit]
        truncated = True

    if not object_ids:
        return CheckResult("history_large_blobs", "pass", "No history objects found")

    batch = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        cwd=str(path),
        input="\n".join(object_ids) + "\n",
        capture_output=True,
        text=True,
    )
    if batch.returncode != 0:
        return CheckResult(
            "history_large_blobs",
            "warn",
            "Could not inspect object sizes for history scan",
            "Run 'git cat-file --batch-check' manually and inspect large blobs.",
        )

    threshold = max_blob_kib * 1024
    oversized: list[tuple[str, int]] = []
    for line in batch.stdout.splitlines():
        parts = line.strip().split(" ")
        if len(parts) != 3:
            continue
        oid, obj_type, size_s = parts
        if obj_type != "blob":
            continue
        try:
            size = int(size_s)
        except ValueError:
            continue
        if size <= threshold:
            continue
        label = first_path.get(oid, oid[:12])
        oversized.append((label, size))

    if not oversized:
        suffix = " (object scan truncated)" if truncated else ""
        return CheckResult(
            "history_large_blobs",
            "pass",
            f"No history blobs above {max_blob_kib} KiB{suffix}",
        )

    oversized.sort(key=lambda x: x[1], reverse=True)
    preview = ", ".join(f"{name} ({size // 1024} KiB)" for name, size in oversized[:5])
    more = "" if len(oversized) <= 5 else f" (+{len(oversized) - 5} more)"
    trunc_note = f"; scanned first {object_limit} objects" if truncated else ""
    return CheckResult(
        "history_large_blobs",
        "warn",
        f"History blobs exceed {max_blob_kib} KiB: {preview}{more}{trunc_note}",
        "Use Git LFS, rewrite history when appropriate, and avoid committing large binary assets.",
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


CHECK_REGISTRY = {
    "git_repository": check_git_repository,
    "remote_origin": check_remote_origin,
    "clean_worktree": check_clean_worktree,
    "default_branch_style": check_default_branch,
    "readme_present": check_readme,
    "license_present": check_license,
    "license_identifier": check_license_spdx,
    "security_policy_present": check_security,
    "gitignore_basics": check_gitignore_secrets,
    "tracked_env_files": check_tracked_env,
    "tracked_keylike_files": check_tracked_keylike_files,
    "tracked_large_files": check_tracked_large_files,
    "history_large_blobs": check_history_large_blobs,
    "gitleaks_scan": check_gitleaks,
}

PROFILE_CHECK_IDS = {
    "quick": [
        "git_repository",
        "readme_present",
        "license_present",
        "security_policy_present",
        "gitignore_basics",
        "tracked_env_files",
        "tracked_keylike_files",
    ],
    "full": list(CHECK_REGISTRY.keys()),
    "ci": list(CHECK_REGISTRY.keys()),
}


def available_check_ids() -> list[str]:
    return list(CHECK_REGISTRY.keys())


def check_ids_for_profile(profile: str) -> list[str]:
    if profile not in PROFILE_CHECK_IDS:
        raise ValueError(f"Unknown profile: {profile}")
    return list(PROFILE_CHECK_IDS[profile])


def validate_check_ids(check_ids: list[str]) -> list[str]:
    unknown = [check_id for check_id in check_ids if check_id not in CHECK_REGISTRY]
    return unknown


def _apply_status_override(result: CheckResult, override_status: str) -> CheckResult:
    if override_status not in VALID_STATUSES or override_status == result.status:
        return result

    return CheckResult(
        id=result.id,
        status=override_status,
        message=f"{result.message} (severity overridden to {override_status})",
        fix=result.fix,
    )


def run_checks(
    path: Path,
    *,
    check_ids: list[str],
    severity_overrides: dict[str, str] | None = None,
    max_tracked_file_kib: int = DEFAULT_MAX_TRACKED_FILE_KIB,
    max_history_blob_kib: int = DEFAULT_MAX_HISTORY_BLOB_KIB,
    history_object_limit: int = DEFAULT_HISTORY_OBJECT_LIMIT,
) -> list[CheckResult]:
    unknown = validate_check_ids(check_ids)
    if unknown:
        unknown_s = ", ".join(unknown)
        raise ValueError(f"Unknown check ids: {unknown_s}")

    severity_overrides = severity_overrides or {}
    results: list[CheckResult] = []
    for check_id in check_ids:
        if check_id == "tracked_large_files":
            result = check_tracked_large_files(path, max_file_kib=max_tracked_file_kib)
        elif check_id == "history_large_blobs":
            result = check_history_large_blobs(
                path,
                max_blob_kib=max_history_blob_kib,
                object_limit=history_object_limit,
            )
        else:
            result = CHECK_REGISTRY[check_id](path)

        if check_id in severity_overrides:
            result = _apply_status_override(result, severity_overrides[check_id])

        results.append(result)

    return results
