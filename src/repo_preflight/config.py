from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib

from .rulepacks import available_rule_packs


VALID_PROFILES = {"quick", "full", "ci"}
VALID_STATUSES = {"pass", "warn", "fail"}
VALID_RULE_PACKS = set(available_rule_packs())
VALID_DIFF_MODES = {"manual", "pr"}


@dataclass
class PreflightConfig:
    profile: str | None = None
    rule_pack: str | None = None
    strict: bool | None = None
    no_gitleaks: bool | None = None
    diff_mode: str | None = None
    pr_base_ref: str | None = None
    diff_base: str | None = None
    diff_target: str | None = None
    max_tracked_file_kib: int | None = None
    max_history_blob_kib: int | None = None
    history_object_limit: int | None = None
    max_diff_files: int | None = None
    max_diff_changed_lines: int | None = None
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    severity_overrides: dict[str, str] = field(default_factory=dict)


def _as_bool(value: object, *, key: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"Config key '{key}' must be boolean")


def _as_str(value: object, *, key: str) -> str:
    if isinstance(value, str):
        return value
    raise ValueError(f"Config key '{key}' must be string")


def _as_positive_int(value: object, *, key: str) -> int:
    if isinstance(value, int) and value > 0:
        return value
    raise ValueError(f"Config key '{key}' must be a positive integer")


def _as_str_list(value: object, *, key: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise ValueError(f"Config key '{key}' must be an array of strings")
    return value


def load_config(path: Path) -> PreflightConfig:
    if not path.exists():
        return PreflightConfig()

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    cfg = PreflightConfig()

    preflight = data.get("preflight", {})
    if preflight:
        if not isinstance(preflight, dict):
            raise ValueError("[preflight] must be a table")

        if "profile" in preflight:
            profile = _as_str(preflight["profile"], key="preflight.profile")
            if profile not in VALID_PROFILES:
                raise ValueError("preflight.profile must be one of: quick, full, ci")
            cfg.profile = profile

        if "rule_pack" in preflight:
            rule_pack = _as_str(preflight["rule_pack"], key="preflight.rule_pack")
            if rule_pack not in VALID_RULE_PACKS:
                allowed = ", ".join(sorted(VALID_RULE_PACKS))
                raise ValueError(f"preflight.rule_pack must be one of: {allowed}")
            cfg.rule_pack = rule_pack

        if "strict" in preflight:
            cfg.strict = _as_bool(preflight["strict"], key="preflight.strict")

        if "no_gitleaks" in preflight:
            cfg.no_gitleaks = _as_bool(preflight["no_gitleaks"], key="preflight.no_gitleaks")

        if "diff_mode" in preflight:
            diff_mode = _as_str(preflight["diff_mode"], key="preflight.diff_mode")
            if diff_mode not in VALID_DIFF_MODES:
                raise ValueError("preflight.diff_mode must be one of: manual, pr")
            cfg.diff_mode = diff_mode

        if "pr_base_ref" in preflight:
            cfg.pr_base_ref = _as_str(preflight["pr_base_ref"], key="preflight.pr_base_ref")

        if "diff_base" in preflight:
            cfg.diff_base = _as_str(preflight["diff_base"], key="preflight.diff_base")

        if "diff_target" in preflight:
            cfg.diff_target = _as_str(preflight["diff_target"], key="preflight.diff_target")

        if "max_tracked_file_kib" in preflight:
            cfg.max_tracked_file_kib = _as_positive_int(
                preflight["max_tracked_file_kib"], key="preflight.max_tracked_file_kib"
            )

        if "max_history_blob_kib" in preflight:
            cfg.max_history_blob_kib = _as_positive_int(
                preflight["max_history_blob_kib"], key="preflight.max_history_blob_kib"
            )

        if "history_object_limit" in preflight:
            cfg.history_object_limit = _as_positive_int(
                preflight["history_object_limit"], key="preflight.history_object_limit"
            )

        if "max_diff_files" in preflight:
            cfg.max_diff_files = _as_positive_int(
                preflight["max_diff_files"], key="preflight.max_diff_files"
            )

        if "max_diff_changed_lines" in preflight:
            cfg.max_diff_changed_lines = _as_positive_int(
                preflight["max_diff_changed_lines"], key="preflight.max_diff_changed_lines"
            )

    checks = data.get("checks", {})
    if checks:
        if not isinstance(checks, dict):
            raise ValueError("[checks] must be a table")

        if "include" in checks:
            cfg.include = _as_str_list(checks["include"], key="checks.include")

        if "exclude" in checks:
            cfg.exclude = _as_str_list(checks["exclude"], key="checks.exclude")

    severity = data.get("severity_overrides", {})
    if severity:
        if not isinstance(severity, dict):
            raise ValueError("[severity_overrides] must be a table")

        for check_id, status in severity.items():
            if not isinstance(check_id, str):
                raise ValueError("severity override keys must be check ids")
            if not isinstance(status, str) or status not in VALID_STATUSES:
                raise ValueError(
                    f"severity_overrides.{check_id} must be one of: pass, warn, fail"
                )
            cfg.severity_overrides[check_id] = status

    return cfg
