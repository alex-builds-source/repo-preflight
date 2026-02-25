from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib


VALID_PROFILES = {"quick", "full", "ci"}
VALID_STATUSES = {"pass", "warn", "fail"}


@dataclass
class PreflightConfig:
    profile: str | None = None
    strict: bool | None = None
    no_gitleaks: bool | None = None
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

        if "strict" in preflight:
            cfg.strict = _as_bool(preflight["strict"], key="preflight.strict")

        if "no_gitleaks" in preflight:
            cfg.no_gitleaks = _as_bool(preflight["no_gitleaks"], key="preflight.no_gitleaks")

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
