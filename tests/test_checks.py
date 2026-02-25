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
    assert statuses["history_large_blobs"] == "pass"
    assert statuses["diff_object_sizes"] == "pass"
    assert statuses["diff_patch_size"] == "pass"


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


def test_history_large_blob_warns_even_if_not_tracked_anymore(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write(repo, "README.md", "# Demo\n")
    _write_bytes(repo, "assets/old-large.bin", 4096)
    _commit_all(repo, "add large blob")
    _run(["git", "rm", "assets/old-large.bin"], repo)
    _commit_all(repo, "remove large blob")

    results = run_checks(
        repo,
        check_ids=["tracked_large_files", "history_large_blobs"],
        max_tracked_file_kib=1,
        max_history_blob_kib=1,
    )
    status_by_id = {r.id: r.status for r in results}
    assert status_by_id["tracked_large_files"] == "pass"
    assert status_by_id["history_large_blobs"] == "warn"


def test_diff_checks_skip_without_base(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write(repo, "README.md", "# Demo\n")
    _commit_all(repo)

    results = run_checks(repo, check_ids=["diff_changed_files", "diff_large_files", "diff_patch_size"])
    status_by_id = {r.id: r.status for r in results}
    assert status_by_id["diff_changed_files"] == "pass"
    assert status_by_id["diff_large_files"] == "pass"
    assert status_by_id["diff_patch_size"] == "pass"


def test_diff_patch_size_warns_for_big_change(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write(repo, "README.md", "# Demo\n")
    _commit_all(repo, "base")

    _run(["git", "checkout", "-b", "feature/diff"], repo)
    _write(repo, "README.md", "# Demo\n" + ("line\n" * 200))
    _write(repo, "new.txt", "".join(f"x{i}\n" for i in range(150)))
    _commit_all(repo, "big diff")

    results = run_checks(
        repo,
        check_ids=["diff_patch_size"],
        diff_base="main",
        diff_target="HEAD",
        max_diff_files=1,
        max_diff_changed_lines=50,
    )
    assert results[0].id == "diff_patch_size"
    assert results[0].status == "warn"


def test_diff_object_sizes_warn_for_large_changed_blob(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write(repo, "README.md", "# Demo\n")
    _commit_all(repo, "base")

    _run(["git", "checkout", "-b", "feature/blob"], repo)
    _write_bytes(repo, "assets/new-large.bin", 4096)
    _commit_all(repo, "add large object")

    results = run_checks(
        repo,
        check_ids=["diff_object_sizes"],
        diff_base="main",
        diff_target="HEAD",
        max_diff_object_kib=1,
    )
    assert results[0].id == "diff_object_sizes"
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
