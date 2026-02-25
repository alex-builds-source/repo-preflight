from __future__ import annotations

from pathlib import Path

from repo_preflight.cli import (
    build_payload,
    exit_code,
    profile_defaults,
    resolve_runtime,
)
from repo_preflight.checks import CheckResult
from repo_preflight.config import PreflightConfig


class ArgsStub:
    def __init__(self, *, profile=None, strict=None, gitleaks=None):
        self.profile = profile
        self.strict = strict
        self.gitleaks = gitleaks


def test_exit_code_priority_default_mode():
    assert exit_code({"pass": 7, "warn": 0, "fail": 0}) == 0
    assert exit_code({"pass": 5, "warn": 1, "fail": 0}) == 1
    assert exit_code({"pass": 4, "warn": 1, "fail": 2}) == 2


def test_exit_code_priority_strict_mode():
    assert exit_code({"pass": 7, "warn": 0, "fail": 0}, strict=True) == 0
    assert exit_code({"pass": 5, "warn": 1, "fail": 0}, strict=True) == 2
    assert exit_code({"pass": 4, "warn": 1, "fail": 2}, strict=True) == 2


def test_json_payload_fields():
    results = [
        CheckResult("sample_warn", "warn", "warning"),
        CheckResult("sample_pass", "pass", "ok"),
    ]
    payload = build_payload(
        Path("/tmp/repo"),
        results,
        strict=True,
        profile="ci",
        check_ids=["sample_warn", "sample_pass"],
        config_path="/tmp/repo/.repo-preflight.toml",
    )
    assert payload["strict"] is True
    assert payload["profile"] == "ci"
    assert payload["config_path"] == "/tmp/repo/.repo-preflight.toml"
    assert payload["exit_code"] == 2
    assert payload["summary"] == {"pass": 1, "warn": 1, "fail": 0}


def test_profile_defaults():
    assert profile_defaults("quick") == {"strict": False, "gitleaks": False}
    assert profile_defaults("full") == {"strict": False, "gitleaks": True}
    assert profile_defaults("ci") == {"strict": True, "gitleaks": True}


def test_resolve_runtime_merges_cli_over_config():
    cfg = PreflightConfig(profile="quick", strict=False, no_gitleaks=True)
    args = ArgsStub(profile="ci", strict=False, gitleaks=True)

    profile, strict, gitleaks_enabled, check_ids, _ = resolve_runtime(args, cfg)
    assert profile == "ci"
    assert strict is False
    assert gitleaks_enabled is True
    assert "gitleaks_scan" in check_ids
