from __future__ import annotations

import subprocess
from pathlib import Path

from repo_preflight.checks import check_ids_for_profile, run_checks


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _init_repo(path: Path) -> None:
    _run(["git", "init", "-b", "main"], path)
    _run(["git", "config", "user.name", "Test"], path)
    _run(["git", "config", "user.email", "test@example.com"], path)


def _write(path: Path, rel: str, content: str) -> None:
    full = path / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _write_bytes(path: Path, rel: str, size: int) -> None:
    full = path / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(b"A" * size)


def _commit_all(path: Path, msg: str = "commit") -> None:
    _run(["git", "add", "-A"], path)
    _run(["git", "commit", "-m", msg], path)


def _add_origin(path: Path, tmp_path: Path) -> None:
    bare = tmp_path / "origin.git"
    _run(["git", "init", "--bare", str(bare)], tmp_path)
    _run(["git", "remote", "add", "origin", str(bare)], path)


def _full_without_gitleaks() -> list[str]:
    return [c for c in check_ids_for_profile("full") if c != "gitleaks_scan"]


def test_happy_path_without_gitleaks(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _add_origin(repo, tmp_path)
    _write(repo, "README.md", "# Demo\n")
    _write(repo, "LICENSE", "SPDX-License-Identifier: MIT\n\nMIT License\n")
    _write(repo, "SECURITY.md", "policy\n")
    _write(repo, ".gitignore", ".env\n.env.*\n!.env.example\n")
    _write(repo, ".env.example", "X=1\n")
    _commit_all(repo)

    results = run_checks(repo, check_ids=_full_without_gitleaks())
    statuses = {r.id: r.status for r in results}
    assert statuses["git_repository"] == "pass"
    assert statuses["remote_origin"] == "pass"
    assert statuses["clean_worktree"] == "pass"
    assert statuses["default_branch_style"] == "pass"
    assert statuses["readme_present"] == "pass"
    assert statuses["license_present"] == "pass"
    assert statuses["license_identifier"] == "pass"
    assert statuses["security_policy_present"] == "pass"
    assert statuses["gitignore_basics"] == "pass"
    assert statuses["tracked_env_files"] == "pass"
    assert statuses["tracked_keylike_files"] == "pass"
    assert statuses["tracked_large_files"] == "pass"


def test_tracked_env_file_fails(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write(repo, "README.md", "# Demo\n")
    _write(repo, "SECURITY.md", "policy\n")
    _write(repo, ".gitignore", ".env\n.env.*\n!.env.example\n")
    _write(repo, ".env", "SECRET=abc\n")
    _run(["git", "add", "-f", ".env"], repo)
    _commit_all(repo)

    results = run_checks(repo, check_ids=_full_without_gitleaks())
    status_by_id = {r.id: r.status for r in results}
    assert status_by_id["tracked_env_files"] == "fail"


def test_missing_readme_fails(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write(repo, "SECURITY.md", "policy\n")
    _write(repo, ".gitignore", ".env\n.env.*\n!.env.example\n")
    _commit_all(repo)

    results = run_checks(repo, check_ids=_full_without_gitleaks())
    status_by_id = {r.id: r.status for r in results}
    assert status_by_id["readme_present"] == "fail"


def test_remote_origin_warns_when_missing(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write(repo, "README.md", "# Demo\n")
    _write(repo, "SECURITY.md", "policy\n")
    _write(repo, ".gitignore", ".env\n.env.*\n!.env.example\n")
    _commit_all(repo)

    results = run_checks(repo, check_ids=_full_without_gitleaks())
    status_by_id = {r.id: r.status for r in results}
    assert status_by_id["remote_origin"] == "warn"


def test_unrecognized_branch_warns(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write(repo, "README.md", "# Demo\n")
    _write(repo, "SECURITY.md", "policy\n")
    _write(repo, ".gitignore", ".env\n.env.*\n!.env.example\n")
    _commit_all(repo)
    _run(["git", "checkout", "-b", "feature/x"], repo)

    results = run_checks(repo, check_ids=_full_without_gitleaks())
    status_by_id = {r.id: r.status for r in results}
    assert status_by_id["default_branch_style"] == "warn"


def test_large_tracked_file_warns_with_low_threshold(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_bytes(repo, "assets/big.bin", 4096)
    _commit_all(repo)

    results = run_checks(repo, check_ids=["tracked_large_files"], max_tracked_file_kib=1)
    assert len(results) == 1
    assert results[0].id == "tracked_large_files"
    assert results[0].status == "warn"


def test_severity_override_changes_status(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write(repo, "README.md", "# Demo\n")
    _commit_all(repo)

    results = run_checks(
        repo,
        check_ids=["license_present"],
        severity_overrides={"license_present": "fail"},
    )
    assert results[0].status == "fail"
