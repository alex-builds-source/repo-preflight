from __future__ import annotations

from pathlib import Path

from repo_preflight.cli import build_payload, exit_code
from repo_preflight.checks import CheckResult


def test_exit_code_priority_default_mode():
    assert exit_code({"pass": 7, "warn": 0, "fail": 0}) == 0
    assert exit_code({"pass": 5, "warn": 1, "fail": 0}) == 1
    assert exit_code({"pass": 4, "warn": 1, "fail": 2}) == 2


def test_exit_code_priority_strict_mode():
    assert exit_code({"pass": 7, "warn": 0, "fail": 0}, strict=True) == 0
    assert exit_code({"pass": 5, "warn": 1, "fail": 0}, strict=True) == 2
    assert exit_code({"pass": 4, "warn": 1, "fail": 2}, strict=True) == 2


def test_json_payload_has_strict_and_exit_code():
    results = [
        CheckResult("sample_warn", "warn", "warning"),
        CheckResult("sample_pass", "pass", "ok"),
    ]
    payload = build_payload(Path("/tmp/repo"), results, strict=True)
    assert payload["strict"] is True
    assert payload["exit_code"] == 2
    assert payload["summary"] == {"pass": 1, "warn": 1, "fail": 0}
