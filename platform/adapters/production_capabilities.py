"""Replaceable local production capability registry."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import Any, Callable, Mapping


class ProductionCapabilityError(RuntimeError):
    pass


CapabilityHandler = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ProductionCapability:
    capability: str
    provider_id: str
    enabled: bool
    metadata: Mapping[str, Any]
    priority: int = 100
    healthy: bool = True


class ProductionCapabilityRegistry:
    """Maps stable workflow capabilities to replaceable local implementations."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._providers: dict[tuple[str, str], tuple[ProductionCapability, CapabilityHandler]] = {}
        self._cursor: dict[str, int] = {}

    def register(self, capability: str, provider_id: str, handler: CapabilityHandler, *, enabled: bool = True,
                 metadata: Mapping[str, Any] | None = None, priority: int = 100, healthy: bool = True,
                 replace: bool = False, replace_provider: bool = False) -> ProductionCapability:
        capability, provider_id = capability.strip(), provider_id.strip()
        if not capability or not provider_id or not callable(handler):
            raise ProductionCapabilityError("capability, provider and handler are required")
        if priority < 0:
            raise ProductionCapabilityError("provider priority must be non-negative")
        definition = ProductionCapability(capability, provider_id, enabled, MappingProxyType(dict(metadata or {})), priority, healthy)
        key = (capability, provider_id)
        with self._lock:
            if replace:
                self._providers = {item_key:item for item_key, item in self._providers.items() if item_key[0] != capability}
            elif key in self._providers and not replace_provider:
                raise ProductionCapabilityError(f"capability provider already registered: {capability}/{provider_id}")
            self._providers[key] = (definition, handler)
        return definition

    def unregister(self, capability: str, provider_id: str | None = None) -> bool:
        with self._lock:
            targets = [key for key in self._providers if key[0] == capability and (provider_id is None or key[1] == provider_id)]
            for key in targets: del self._providers[key]
            return bool(targets)

    def has(self, capability: str, provider_id: str | None = None) -> bool:
        with self._lock:
            return any(key[0] == capability and (provider_id is None or key[1] == provider_id) for key in self._providers)

    def get(self, capability: str, provider_id: str | None = None) -> ProductionCapability:
        with self._lock:
            return self._entry(capability, provider_id, include_unavailable=provider_id is not None)[0]

    def enable(self, capability: str, enabled: bool, provider_id: str | None = None) -> ProductionCapability:
        with self._lock:
            targets = [key for key in self._providers if key[0] == capability and (provider_id is None or key[1] == provider_id)]
            if not targets: raise ProductionCapabilityError(f"capability is not installed: {capability}")
            updated_items = []
            for key in targets:
                definition, handler = self._providers[key]
                updated = ProductionCapability(definition.capability, definition.provider_id, enabled, definition.metadata, definition.priority, definition.healthy)
                self._providers[key] = (updated, handler); updated_items.append(updated)
            return sorted(updated_items, key=lambda item:(item.priority, item.provider_id))[0]

    def health(self, capability: str, provider_id: str, healthy: bool) -> ProductionCapability:
        with self._lock:
            definition, handler = self._entry(capability, provider_id, include_unavailable=True)
            updated = ProductionCapability(definition.capability, definition.provider_id, definition.enabled, definition.metadata, definition.priority, healthy)
            self._providers[(capability, provider_id)] = (updated, handler)
            return updated

    def invoke(self, capability: str, /, *, provider_id: str | None = None, allow_fallback: bool = False, **inputs: Any) -> Any:
        return self.invoke_with_provider(capability, provider_id=provider_id, allow_fallback=allow_fallback, **inputs)[1]

    def invoke_with_provider(self, capability: str, /, *, provider_id: str | None = None, allow_fallback: bool = False, **inputs: Any) -> tuple[ProductionCapability, Any]:
        """Invoke and return the exact selected provider with the result."""
        with self._lock:
            entries = self._eligible(capability, provider_id)
        failures = []
        for definition, handler in entries:
            try:
                result = handler(**inputs)
                if result is None: raise ProductionCapabilityError(f"capability returned no result: {capability}/{definition.provider_id}")
                return definition, result
            except Exception as error:
                failures.append(f"{definition.provider_id}:{error}")
                if not allow_fallback: raise
        raise ProductionCapabilityError(f"all providers failed for {capability}: {'; '.join(failures)}")

    def list(self) -> tuple[ProductionCapability, ...]:
        with self._lock:
            return tuple(sorted((entry[0] for entry in self._providers.values()), key=lambda item:(item.capability, item.priority, item.provider_id)))

    def _eligible(self, capability: str, provider_id: str | None = None) -> list[tuple[ProductionCapability, CapabilityHandler]]:
        entries = [entry for key, entry in self._providers.items() if key[0] == capability and (provider_id is None or key[1] == provider_id)]
        if not entries: raise ProductionCapabilityError(f"capability is not installed: {capability}")
        eligible = [entry for entry in entries if entry[0].enabled and entry[0].healthy]
        if not eligible: raise ProductionCapabilityError(f"capability has no healthy enabled provider: {capability}")
        eligible.sort(key=lambda entry:(entry[0].priority, entry[0].provider_id))
        if provider_id is None:
            best_priority = eligible[0][0].priority
            peers = [entry for entry in eligible if entry[0].priority == best_priority]
            cursor = self._cursor.get(capability, 0) % len(peers); self._cursor[capability] = cursor + 1
            selected = peers[cursor]
            eligible = [selected, *[entry for entry in eligible if entry is not selected]]
        return eligible

    def _entry(self, capability: str, provider_id: str | None = None, *, include_unavailable: bool = False) -> tuple[ProductionCapability, CapabilityHandler]:
        if include_unavailable and provider_id is not None:
            try: return self._providers[(capability, provider_id)]
            except KeyError as error: raise ProductionCapabilityError(f"capability provider is not installed: {capability}/{provider_id}") from error
        return self._eligible(capability, provider_id)[0]


_DEFAULT_REGISTRY = ProductionCapabilityRegistry()


def production_capability_registry() -> ProductionCapabilityRegistry:
    """Return the process-wide registry used by the production kernel and plugins."""
    return _DEFAULT_REGISTRY
