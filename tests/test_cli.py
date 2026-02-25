from __future__ import annotations

from repo_preflight.cli import exit_code


def test_exit_code_priority():
    assert exit_code({"pass": 7, "warn": 0, "fail": 0}) == 0
    assert exit_code({"pass": 5, "warn": 1, "fail": 0}) == 1
    assert exit_code({"pass": 4, "warn": 1, "fail": 2}) == 2
