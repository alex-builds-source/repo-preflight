from __future__ import annotations

from pathlib import Path

from repo_preflight.cli import (
    build_payload,
    build_policy_doc,
    build_policy_template,
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
        max_diff_files=None,
        max_diff_changed_lines=None,
        diff_mode=None,
        pr_base_ref=None,
        diff_base=None,
        diff_target=None,
    ):
        self.profile = profile
        self.rule_pack = rule_pack
        self.strict = strict
        self.gitleaks = gitleaks
        self.max_file_kib = max_file_kib
        self.max_history_kib = max_history_kib
        self.history_object_limit = history_object_limit
        self.max_diff_files = max_diff_files
        self.max_diff_changed_lines = max_diff_changed_lines
        self.diff_mode = diff_mode
        self.pr_base_ref = pr_base_ref
        self.diff_base = diff_base
        self.diff_target = diff_target


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
        max_diff_files=222,
        max_diff_changed_lines=3333,
        diff_mode="pr",
        pr_base_ref="origin/main",
        diff_base="origin/main",
        diff_target="HEAD",
    )
    assert payload["strict"] is True
    assert payload["profile"] == "ci"
    assert payload["rule_pack"] == "oss-library"
    assert payload["max_diff_files"] == 222
    assert payload["max_diff_changed_lines"] == 3333
    assert payload["diff_mode"] == "pr"
    assert payload["pr_base_ref"] == "origin/main"
    assert payload["diff_base"] == "origin/main"
    assert payload["diff_target"] == "HEAD"
    assert payload["exit_code"] == 2


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
        diff_mode="pr",
        pr_base_ref="origin/main",
        diff_base="origin/main",
        diff_target="HEAD",
    )
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "repo-preflight"
    assert len(run["results"]) == 2
    assert run["properties"]["diff_mode"] == "pr"


def test_policy_doc_contains_effective_settings():
    doc = build_policy_doc(
        path=Path("/tmp/repo"),
        profile="ci",
        rule_pack="oss-library",
        strict=True,
        gitleaks_enabled=True,
        diff_mode="pr",
        pr_base_ref="origin/main",
        diff_base="origin/main",
        diff_target="HEAD",
        max_tracked_file_kib=2048,
        max_history_blob_kib=4096,
        history_object_limit=15000,
        max_diff_files=200,
        max_diff_changed_lines=4000,
        check_ids=["readme_present", "gitleaks_scan"],
        severity_overrides={"license_present": "fail"},
        config_path="/tmp/repo/.repo-preflight.toml",
    )
    assert "# repo-preflight policy" in doc
    assert "Profile: `ci`" in doc
    assert "Max diff files: `200`" in doc
    assert "`license_present` -> `fail`" in doc


def test_policy_template_contains_rule_pack_defaults():
    template = build_policy_template(rule_pack_name="oss-library", profile="ci")
    assert 'rule_pack = "oss-library"' in template
    assert 'diff_mode = "pr"' in template
    assert 'license_present = "fail"' in template


def test_profile_defaults():
    assert profile_defaults("quick") == {"strict": False, "gitleaks": False}
    assert profile_defaults("full") == {"strict": False, "gitleaks": True}
    assert profile_defaults("ci") == {"strict": True, "gitleaks": True}


def test_resolve_runtime_merges_cli_over_config():
    cfg = PreflightConfig(
        profile="quick",
        strict=False,
        no_gitleaks=True,
        diff_mode="manual",
        pr_base_ref="origin/main",
        diff_base="origin/main",
        diff_target="HEAD",
        max_tracked_file_kib=1024,
        max_history_blob_kib=2048,
        history_object_limit=6000,
        max_diff_files=50,
        max_diff_changed_lines=500,
    )
    args = ArgsStub(
        profile="ci",
        strict=False,
        gitleaks=True,
        max_file_kib=4096,
        max_history_kib=8192,
        history_object_limit=1000,
        max_diff_files=100,
        max_diff_changed_lines=999,
        diff_mode="manual",
        pr_base_ref="origin/develop",
        diff_base="origin/develop",
        diff_target="HEAD~1",
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
        max_diff_files,
        max_diff_changed_lines,
        diff_mode,
        pr_base_ref,
        diff_base,
        diff_target,
    ) = resolve_runtime(args, cfg)
    assert profile == "ci"
    assert rule_pack is None
    assert strict is False
    assert gitleaks_enabled is True
    assert "gitleaks_scan" in check_ids
    assert max_file_kib == 4096
    assert max_history_kib == 8192
    assert history_limit == 1000
    assert max_diff_files == 100
    assert max_diff_changed_lines == 999
    assert diff_mode == "manual"
    assert pr_base_ref == "origin/develop"
    assert diff_base == "origin/develop"
    assert diff_target == "HEAD~1"


def test_resolve_runtime_pr_mode_uses_ci_env(monkeypatch):
    cfg = PreflightConfig(diff_mode="pr")
    args = ArgsStub(diff_mode="pr")

    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    monkeypatch.setenv("GITHUB_SHA", "abc123")

    (
        _profile,
        _rule_pack,
        _strict,
        _gitleaks,
        _checks,
        _overrides,
        _max_file_kib,
        _max_history_kib,
        _history_limit,
        _max_diff_files,
        _max_diff_changed_lines,
        diff_mode,
        _pr_base_ref,
        diff_base,
        diff_target,
    ) = resolve_runtime(args, cfg)

    assert diff_mode == "pr"
    assert diff_base == "origin/main"
    assert diff_target == "abc123"


def test_rule_pack_applies_when_selected():
    cfg = PreflightConfig()
    args = ArgsStub(rule_pack="oss-library")

    (
        _profile,
        rule_pack,
        strict,
        _gitleaks,
        _checks,
        overrides,
        _a,
        _b,
        _c,
        _d,
        _e,
        _f,
        _g,
        _h,
        _i,
    ) = resolve_runtime(args, cfg)
    assert rule_pack == "oss-library"
    assert strict is True
    assert overrides.get("license_present") == "fail"
