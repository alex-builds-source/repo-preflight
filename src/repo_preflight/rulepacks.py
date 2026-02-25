from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RulePack:
    name: str
    description: str
    strict: bool | None = None
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    severity_overrides: dict[str, str] = field(default_factory=dict)


RULE_PACKS: dict[str, RulePack] = {
    "oss-library": RulePack(
        name="oss-library",
        description="Open-source library defaults with stronger docs/license expectations.",
        strict=True,
        severity_overrides={
            "license_present": "fail",
            "license_identifier": "fail",
            "security_policy_present": "fail",
        },
    ),
    "internal-service": RulePack(
        name="internal-service",
        description="Internal service defaults with repo hygiene and secret controls.",
        strict=True,
        severity_overrides={
            "remote_origin": "fail",
            "license_present": "pass",
            "license_identifier": "pass",
            "security_policy_present": "warn",
        },
    ),
    "cli-tool": RulePack(
        name="cli-tool",
        description="CLI tool defaults with balanced public-release expectations.",
        strict=False,
        severity_overrides={
            "license_present": "fail",
            "license_identifier": "warn",
            "security_policy_present": "warn",
        },
    ),
}


def available_rule_packs() -> list[str]:
    return list(RULE_PACKS.keys())


def get_rule_pack(name: str) -> RulePack:
    if name not in RULE_PACKS:
        raise ValueError(f"Unknown rule pack: {name}")
    return RULE_PACKS[name]
