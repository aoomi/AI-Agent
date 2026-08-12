"""Validated identity context propagated through platform operations."""

from __future__ import annotations

from dataclasses import dataclass


IDENTITY_KINDS = frozenset({"user", "service", "agent"})


class IdentityContextError(ValueError):
    """Raised when required identity scope is absent or invalid."""


def _required(value: str, field_name: str) -> str:
    if not isinstance(value,str):
        raise IdentityContextError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise IdentityContextError(f"{field_name} must not be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class IdentityContext:
    request_id: str
    trace_id: str
    identity_id: str
    identity_kind: str
    tenant_id: str

    def __post_init__(self) -> None:
        for field_name in ("request_id", "trace_id", "identity_id", "tenant_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        normalized_kind = _required(self.identity_kind,"identity_kind")
        if normalized_kind not in IDENTITY_KINDS:
            raise IdentityContextError("identity_kind is not supported")
        object.__setattr__(self, "identity_kind", normalized_kind)

    def require_tenant(self, tenant_id: str) -> None:
        if self.tenant_id != _required(tenant_id, "tenant_id"):
            raise IdentityContextError("tenant scope mismatch")

    def event_scope(self) -> dict[str, str]:
        return {
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "identity_id": self.identity_id,
            "tenant_id": self.tenant_id,
        }
