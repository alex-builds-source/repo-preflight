from __future__ import annotations

from pathlib import Path

from repo_preflight.cli import (
    build_payload,
    build_sarif_payload,
    exit_code,
    profile_defaults,
    resolve_runtime,
)
from repo_preflight.checks import CheckResult
from repo_preflight.config import PreflightConfig


class ArgsStub:
    def __init__(
        self,
        *,
        profile=None,
        rule_pack=None,
        strict=None,
        gitleaks=None,
        max_file_kib=None,
        max_history_kib=None,
        history_object_limit=None,
    ):
        self.profile = profile
        self.rule_pack = rule_pack
        self.strict = strict
        self.gitleaks = gitleaks
        self.max_file_kib = max_file_kib
        self.max_history_kib = max_history_kib
        self.history_object_limit = history_object_limit


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
        rule_pack="oss-library",
        check_ids=["sample_warn", "sample_pass"],
        config_path="/tmp/repo/.repo-preflight.toml",
        max_tracked_file_kib=2048,
        max_history_blob_kib=4096,
        history_object_limit=15000,
    )
    assert payload["strict"] is True
    assert payload["profile"] == "ci"
    assert payload["rule_pack"] == "oss-library"
    assert payload["config_path"] == "/tmp/repo/.repo-preflight.toml"
    assert payload["max_tracked_file_kib"] == 2048
    assert payload["max_history_blob_kib"] == 4096
    assert payload["history_object_limit"] == 15000
    assert payload["exit_code"] == 2
    assert payload["summary"] == {"pass": 1, "warn": 1, "fail": 0}


def test_sarif_payload_shape():
    results = [
        CheckResult("readme_present", "fail", "README missing", "Add README"),
        CheckResult("license_present", "warn", "LICENSE missing", "Add LICENSE"),
        CheckResult("git_repository", "pass", "ok"),
    ]
    sarif = build_sarif_payload(
        Path("/tmp/repo"),
        results,
        strict=True,
        profile="ci",
        rule_pack="oss-library",
        check_ids=["readme_present", "license_present", "git_repository"],
        config_path="/tmp/repo/.repo-preflight.toml",
    )
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "repo-preflight"
    assert len(run["results"]) == 2  # pass entries omitted
    assert run["results"][0]["level"] in {"error", "warning"}


def test_profile_defaults():
    assert profile_defaults("quick") == {"strict": False, "gitleaks": False}
    assert profile_defaults("full") == {"strict": False, "gitleaks": True}
    assert profile_defaults("ci") == {"strict": True, "gitleaks": True}


def test_resolve_runtime_merges_cli_over_config():
    cfg = PreflightConfig(
        profile="quick",
        strict=False,
        no_gitleaks=True,
        max_tracked_file_kib=1024,
        max_history_blob_kib=2048,
        history_object_limit=6000,
    )
    args = ArgsStub(
        profile="ci",
        strict=False,
        gitleaks=True,
        max_file_kib=4096,
        max_history_kib=8192,
        history_object_limit=1000,
    )

    (
        profile,
        rule_pack,
        strict,
        gitleaks_enabled,
        check_ids,
        _overrides,
        max_file_kib,
        max_history_kib,
        history_limit,
    ) = resolve_runtime(args, cfg)
    assert profile == "ci"
    assert rule_pack is None
    assert strict is False
    assert gitleaks_enabled is True
    assert "gitleaks_scan" in check_ids
    assert max_file_kib == 4096
    assert max_history_kib == 8192
    assert history_limit == 1000


def test_rule_pack_applies_when_selected():
    cfg = PreflightConfig()
    args = ArgsStub(rule_pack="oss-library")

    _profile, rule_pack, strict, _gitleaks, _checks, overrides, _a, _b, _c = resolve_runtime(args, cfg)
    assert rule_pack == "oss-library"
    assert strict is True
    assert overrides.get("license_present") == "fail"
