from __future__ import annotations

from pathlib import Path

from repo_preflight.config import load_config


def test_load_config_defaults_when_missing(tmp_path: Path):
    cfg = load_config(tmp_path / ".repo-preflight.toml")
    assert cfg.profile is None
    assert cfg.strict is None
    assert cfg.no_gitleaks is None
    assert cfg.include == []
    assert cfg.exclude == []
    assert cfg.severity_overrides == {}


def test_load_config_with_values(tmp_path: Path):
    cfg_path = tmp_path / ".repo-preflight.toml"
    cfg_path.write_text(
        """
[preflight]
profile = "ci"
strict = true
no_gitleaks = false

[checks]
include = ["license_present"]
exclude = ["clean_worktree"]

[severity_overrides]
license_present = "fail"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = load_config(cfg_path)
    assert cfg.profile == "ci"
    assert cfg.strict is True
    assert cfg.no_gitleaks is False
    assert cfg.include == ["license_present"]
    assert cfg.exclude == ["clean_worktree"]
    assert cfg.severity_overrides == {"license_present": "fail"}
