from __future__ import annotations

import subprocess
from pathlib import Path

from repo_preflight.checks import run_checks


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _init_repo(path: Path) -> None:
    _run(["git", "init"], path)
    _run(["git", "config", "user.name", "Test"], path)
    _run(["git", "config", "user.email", "test@example.com"], path)


def _write(path: Path, rel: str, content: str) -> None:
    full = path / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _commit_all(path: Path, msg: str = "commit") -> None:
    _run(["git", "add", "-A"], path)
    _run(["git", "commit", "-m", msg], path)


def test_happy_path_without_gitleaks(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write(repo, "README.md", "# Demo\n")
    _write(repo, "LICENSE", "MIT\n")
    _write(repo, "SECURITY.md", "policy\n")
    _write(repo, ".gitignore", ".env\n.env.*\n!.env.example\n")
    _write(repo, ".env.example", "X=1\n")
    _commit_all(repo)

    results = run_checks(repo, include_gitleaks=False)
    statuses = {r.id: r.status for r in results}
    assert statuses["readme_present"] == "pass"
    assert statuses["license_present"] == "pass"
    assert statuses["security_policy_present"] == "pass"
    assert statuses["gitignore_basics"] == "pass"
    assert statuses["tracked_env_files"] == "pass"
    assert statuses["tracked_keylike_files"] == "pass"


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

    results = run_checks(repo, include_gitleaks=False)
    status_by_id = {r.id: r.status for r in results}
    assert status_by_id["tracked_env_files"] == "fail"


def test_missing_readme_fails(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write(repo, "SECURITY.md", "policy\n")
    _write(repo, ".gitignore", ".env\n.env.*\n!.env.example\n")
    _commit_all(repo)

    results = run_checks(repo, include_gitleaks=False)
    status_by_id = {r.id: r.status for r in results}
    assert status_by_id["readme_present"] == "fail"
