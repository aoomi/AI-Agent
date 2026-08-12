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
        self._inflight: dict[tuple[str, str], int] = {}

    @staticmethod
    def _contains_sensitive_key(value: Any) -> bool:
        forbidden = ("secret", "token", "password", "api_key", "authorization", "credential")
        if isinstance(value, Mapping):
            return any(
                any(word in str(key).lower() for word in forbidden)
                or ProductionCapabilityRegistry._contains_sensitive_key(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple, set, frozenset)):
            return any(ProductionCapabilityRegistry._contains_sensitive_key(item) for item in value)
        return False

    @classmethod
    def _validate_metadata(cls, metadata: Mapping[str, Any]) -> None:
        if cls._contains_sensitive_key(metadata):
            raise ProductionCapabilityError("provider metadata contain sensitive fields")
        concurrency = metadata.get("max_concurrency")
        if concurrency is not None and (
            isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency <= 0
        ):
            raise ProductionCapabilityError("provider max_concurrency must be a positive integer")

    def register(self, capability: str, provider_id: str, handler: CapabilityHandler, *, enabled: bool = True,
                 metadata: Mapping[str, Any] | None = None, priority: int = 100, healthy: bool = True,
                 replace: bool = False, replace_provider: bool = False) -> ProductionCapability:
        capability, provider_id = capability.strip(), provider_id.strip()
        if not capability or not provider_id or not callable(handler):
            raise ProductionCapabilityError("capability, provider and handler are required")
        if priority < 0:
            raise ProductionCapabilityError("provider priority must be non-negative")
        self._validate_metadata(metadata or {})
        definition = ProductionCapability(capability, provider_id, enabled, MappingProxyType(dict(metadata or {})), priority, healthy)
        key = (capability, provider_id)
        with self._lock:
            if replace and any(count for key, count in self._inflight.items() if key[0] == capability):
                raise ProductionCapabilityError(f"capability has in-flight invocations: {capability}")
            if replace_provider and self._inflight.get(key, 0):
                raise ProductionCapabilityError(f"capability provider has in-flight invocations: {capability}/{provider_id}")
            if replace:
                self._providers = {item_key:item for item_key, item in self._providers.items() if item_key[0] != capability}
            elif key in self._providers and not replace_provider:
                raise ProductionCapabilityError(f"capability provider already registered: {capability}/{provider_id}")
            self._providers[key] = (definition, handler)
        return definition

    def register_once(self, capability: str, provider_id: str, handler: CapabilityHandler, *, enabled: bool = True,
                      metadata: Mapping[str, Any] | None = None, priority: int = 100,
                      healthy: bool = True) -> ProductionCapability:
        """Atomically install a process-lifetime provider without hot-replacing it.

        Built-in installation can be reached through more than one imported API
        module. Reusing the existing provider is configuration discovery, not a
        provider replacement, and must remain safe while that provider is busy.
        """
        capability, provider_id = capability.strip(), provider_id.strip()
        if not capability or not provider_id or not callable(handler):
            raise ProductionCapabilityError("capability, provider and handler are required")
        if priority < 0:
            raise ProductionCapabilityError("provider priority must be non-negative")
        self._validate_metadata(metadata or {})
        key = (capability, provider_id)
        with self._lock:
            existing = self._providers.get(key)
            if existing is not None:
                return existing[0]
            return self.register(
                capability, provider_id, handler, enabled=enabled, metadata=metadata,
                priority=priority, healthy=healthy,
            )

    def unregister(self, capability: str, provider_id: str | None = None) -> bool:
        capability = self._required_id("capability", capability)
        provider_id = self._optional_id("provider", provider_id)
        with self._lock:
            targets = [key for key in self._providers if key[0] == capability and (provider_id is None or key[1] == provider_id)]
            active = [key for key in targets if self._inflight.get(key, 0)]
            if active:
                raise ProductionCapabilityError(f"capability provider has in-flight invocations: {active[0][0]}/{active[0][1]}")
            for key in targets: del self._providers[key]
            return bool(targets)

    def has(self, capability: str, provider_id: str | None = None) -> bool:
        capability = self._required_id("capability", capability)
        provider_id = self._optional_id("provider", provider_id)
        with self._lock:
            return any(key[0] == capability and (provider_id is None or key[1] == provider_id) for key in self._providers)

    def get(self, capability: str, provider_id: str | None = None) -> ProductionCapability:
        capability = self._required_id("capability", capability)
        provider_id = self._optional_id("provider", provider_id)
        with self._lock:
            return self._entry(capability, provider_id, include_unavailable=provider_id is not None)[0]

    def enable(self, capability: str, enabled: bool, provider_id: str | None = None) -> ProductionCapability:
        capability = self._required_id("capability", capability)
        provider_id = self._optional_id("provider", provider_id)
        if not isinstance(enabled, bool):
            raise ProductionCapabilityError("enabled must be boolean")
        with self._lock:
            targets = [key for key in self._providers if key[0] == capability and (provider_id is None or key[1] == provider_id)]
            if not targets: raise ProductionCapabilityError(f"capability is not installed: {capability}")
            active = [key for key in targets if self._inflight.get(key, 0)]
            if not enabled and active:
                raise ProductionCapabilityError(f"capability provider has in-flight invocations: {active[0][0]}/{active[0][1]}")
            updated_items = []
            for key in targets:
                definition, handler = self._providers[key]
                updated = ProductionCapability(definition.capability, definition.provider_id, enabled, definition.metadata, definition.priority, definition.healthy)
                self._providers[key] = (updated, handler); updated_items.append(updated)
            return sorted(updated_items, key=lambda item:(item.priority, item.provider_id))[0]

    def health(self, capability: str, provider_id: str, healthy: bool) -> ProductionCapability:
        capability = self._required_id("capability", capability)
        provider_id = self._required_id("provider", provider_id)
        if not isinstance(healthy, bool):
            raise ProductionCapabilityError("healthy must be boolean")
        with self._lock:
            definition, handler = self._entry(capability, provider_id, include_unavailable=True)
            if not healthy and self._inflight.get((capability, provider_id), 0):
                raise ProductionCapabilityError(f"capability provider has in-flight invocations: {capability}/{provider_id}")
            updated = ProductionCapability(definition.capability, definition.provider_id, definition.enabled, definition.metadata, definition.priority, healthy)
            self._providers[(capability, provider_id)] = (updated, handler)
            return updated

    def invoke(self, capability: str, /, *, provider_id: str | None = None, allow_fallback: bool = False, **inputs: Any) -> Any:
        return self.invoke_with_provider(capability, provider_id=provider_id, allow_fallback=allow_fallback, **inputs)[1]

    def invoke_with_provider(self, capability: str, /, *, provider_id: str | None = None, allow_fallback: bool = False, **inputs: Any) -> tuple[ProductionCapability, Any]:
        """Invoke and return the exact selected provider with the result."""
        capability = self._required_id("capability", capability)
        provider_id = self._optional_id("provider", provider_id)
        if not isinstance(allow_fallback, bool):
            raise ProductionCapabilityError("allow_fallback must be boolean")
        failures = []
        excluded: set[str] = set()
        while True:
            with self._lock:
                entries = [entry for entry in self._eligible(capability, provider_id) if entry[0].provider_id not in excluded]
                reserved = next((entry for entry in entries if self._has_capacity(entry[0])), None)
                if reserved is None:
                    if failures:
                        break
                    raise ProductionCapabilityError(f"capability providers are at concurrency capacity: {capability}")
                definition, handler = reserved
                key = (definition.capability, definition.provider_id)
                self._inflight[key] = self._inflight.get(key, 0) + 1
            try:
                result = handler(**inputs)
                if result is None: raise ProductionCapabilityError(f"capability returned no result: {capability}/{definition.provider_id}")
                return definition, result
            except Exception as error:
                failures.append(f"{definition.provider_id}:{error}")
                if not allow_fallback: raise
                excluded.add(definition.provider_id)
            finally:
                with self._lock:
                    remaining = self._inflight.get(key, 1) - 1
                    if remaining:
                        self._inflight[key] = remaining
                    else:
                        self._inflight.pop(key, None)
        raise ProductionCapabilityError(f"all providers failed for {capability}: {'; '.join(failures)}")

    def list(self) -> tuple[ProductionCapability, ...]:
        with self._lock:
            return tuple(sorted((entry[0] for entry in self._providers.values()), key=lambda item:(item.capability, item.priority, item.provider_id)))

    def runtime_snapshot(self) -> tuple[dict[str, Any], ...]:
        """Return immutable provider configuration plus live concurrency occupancy."""
        with self._lock:
            return tuple({
                "capability":definition.capability, "provider_id":definition.provider_id,
                "enabled":definition.enabled, "healthy":definition.healthy, "priority":definition.priority,
                "inflight":self._inflight.get(key, 0),
                "max_concurrency":definition.metadata.get("max_concurrency"),
            } for key, (definition, _) in sorted(self._providers.items()))

    def _has_capacity(self, definition: ProductionCapability) -> bool:
        limit = definition.metadata.get("max_concurrency")
        return limit is None or self._inflight.get((definition.capability, definition.provider_id), 0) < limit

    @staticmethod
    def _required_id(field_name: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ProductionCapabilityError(f"{field_name} is required")
        return normalized

    @classmethod
    def _optional_id(cls, field_name: str, value: str | None) -> str | None:
        return None if value is None else cls._required_id(field_name, value)

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
