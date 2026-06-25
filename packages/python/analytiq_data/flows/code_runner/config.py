from __future__ import annotations

import os
import sysconfig
from dataclasses import dataclass

from .security import BUILTINS_DENY_DEFAULT

FLOW_CODE_ENV_VARS = (
    "FLOW_CODE_STDLIB_ALLOW",
    "FLOW_CODE_EXTERNAL_ALLOW",
    "FLOW_CODE_BUILTINS_DENY",
    "FLOW_CODE_BLOCK_ENV_ACCESS",
    "FLOW_CODE_ENABLED",
    "FLOW_CODE_MAX_PAYLOAD_BYTES",
    "FLOW_CODE_BINARY_READ_MAX_BYTES",
)

DEFAULT_STDLIB_ALLOW = (
    "json,re,math,datetime,collections,itertools,functools,hashlib,base64,uuid,typing"
)
DEFAULT_MAX_PAYLOAD_BYTES = 33_554_432  # 32 MiB
DEFAULT_BINARY_READ_MAX_BYTES = 16_777_216  # 16 MiB
MAX_PRINT_CALLS = 100


def _parse_csv(value: str | None) -> list[str]:
    if not value or not value.strip():
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_allowlist(value: str | None, default: str) -> set[str]:
    raw = default if value is None or not value.strip() else value
    parts = _parse_csv(raw)
    if not parts:
        return set()
    if len(parts) == 1 and parts[0] == "*":
        return {"*"}
    if "*" in parts:
        raise ValueError("Wildcard '*' cannot be combined with other allowlist entries")
    return set(parts)


@dataclass(frozen=True)
class SecurityConfig:
    stdlib_allow: set[str]
    external_allow: set[str]
    builtins_deny: set[str]
    block_env_access: bool
    enabled: bool
    max_payload_bytes: int
    binary_read_max_bytes: int

    @classmethod
    def from_env(cls) -> SecurityConfig:
        deny_raw = os.environ.get("FLOW_CODE_BUILTINS_DENY")
        if deny_raw is None or not deny_raw.strip():
            deny = set(BUILTINS_DENY_DEFAULT)
        else:
            deny = set(_parse_csv(deny_raw))
        return cls(
            stdlib_allow=_parse_allowlist(
                os.environ.get("FLOW_CODE_STDLIB_ALLOW"), DEFAULT_STDLIB_ALLOW
            ),
            external_allow=_parse_allowlist(os.environ.get("FLOW_CODE_EXTERNAL_ALLOW"), ""),
            builtins_deny=deny,
            block_env_access=os.environ.get("FLOW_CODE_BLOCK_ENV_ACCESS", "true").lower()
            not in ("0", "false", "no"),
            enabled=os.environ.get("FLOW_CODE_ENABLED", "true").lower()
            not in ("0", "false", "no"),
            max_payload_bytes=int(
                os.environ.get("FLOW_CODE_MAX_PAYLOAD_BYTES", str(DEFAULT_MAX_PAYLOAD_BYTES))
            ),
            binary_read_max_bytes=int(
                os.environ.get("FLOW_CODE_BINARY_READ_MAX_BYTES", str(DEFAULT_BINARY_READ_MAX_BYTES))
            ),
        )

    def is_module_allowed(self, module_name: str) -> bool:
        top = module_name.split(".")[0]
        if "*" in self.stdlib_allow or "*" in self.external_allow:
            return True
        return top in self.stdlib_allow or top in self.external_allow

    def cache_key(self) -> str:
        return "|".join(
            [
                ",".join(sorted(self.stdlib_allow)),
                ",".join(sorted(self.external_allow)),
                ",".join(sorted(self.builtins_deny)),
                str(self.block_env_access),
            ]
        )


def flow_code_env_for_child() -> dict[str, str]:
    """Subset of parent env passed to the isolated child (no secrets)."""
    env: dict[str, str] = {}
    if "PATH" in os.environ:
        env["PATH"] = os.environ["PATH"]
    env["FLOW_CODE_SITE_PACKAGES"] = sysconfig.get_path("purelib")
    for key in FLOW_CODE_ENV_VARS:
        value = os.environ.get(key)
        if value is not None and value.strip():
            env[key] = value
    return env
