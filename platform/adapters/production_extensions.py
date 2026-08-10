"""Replaceable infrastructure extension points for the production kernel."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import Any, Callable, Mapping


class ProductionExtensionError(RuntimeError):
    pass


ExtensionFactory = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ProductionExtension:
    extension_point: str
    provider_id: str
    enabled: bool
    metadata: Mapping[str, Any]
    active: bool = False


class ProductionExtensionRegistry:
    """Keeps the production kernel independent from storage and runtime implementations."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._extensions: dict[tuple[str, str], tuple[ProductionExtension, ExtensionFactory]] = {}
        self._active: dict[str, str] = {}

    def register(
        self,
        extension_point: str,
        provider_id: str,
        factory: ExtensionFactory,
        *,
        enabled: bool = True,
        metadata: Mapping[str, Any] | None = None,
        replace: bool = False,
        replace_provider: bool = False,
        activate: bool | None = None,
    ) -> ProductionExtension:
        point, provider = extension_point.strip(), provider_id.strip()
        if not point or not provider or not callable(factory):
            raise ProductionExtensionError("extension point, provider and factory are required")
        key = (point, provider)
        with self._lock:
            was_active = self._active.get(point) == provider
            should_activate = activate if activate is not None else was_active or replace or point not in self._active
            # Validate the complete replacement before mutating the registry.  A
            # rejected replacement must never destroy the currently active
            # infrastructure binding.
            if should_activate and not enabled:
                raise ProductionExtensionError("disabled extension provider cannot be activated")
            if replace:
                self._extensions = {item_key:item for item_key, item in self._extensions.items() if item_key[0] != point}
                self._active.pop(point, None)
            elif key in self._extensions and not replace_provider:
                raise ProductionExtensionError(f"extension provider already registered: {point}/{provider}")
            definition = ProductionExtension(point, provider, enabled, MappingProxyType(dict(metadata or {})), should_activate)
            self._extensions[key] = (definition, factory)
            if should_activate:
                self._activate_locked(point, provider)
            elif self._active.get(point) == provider:
                self._active.pop(point, None)
        return definition

    def unregister(self, extension_point: str, provider_id: str | None = None) -> bool:
        with self._lock:
            targets = [key for key in self._extensions if key[0] == extension_point and (provider_id is None or key[1] == provider_id)]
            was_active = self._active.get(extension_point) in {key[1] for key in targets}
            for key in targets: del self._extensions[key]
            if was_active:
                self._active.pop(extension_point, None)
                candidates = sorted(key[1] for key, entry in self._extensions.items() if key[0] == extension_point and entry[0].enabled)
                if candidates: self._activate_locked(extension_point, candidates[0])
            return bool(targets)

    def enable(self, extension_point: str, enabled: bool, provider_id: str | None = None) -> ProductionExtension:
        with self._lock:
            targets = [key for key in self._extensions if key[0] == extension_point and (provider_id is None or key[1] == provider_id)]
            if not targets: raise ProductionExtensionError(f"extension is not installed: {extension_point}")
            updated_items = []
            for key in targets:
                definition, factory = self._extensions[key]
                active = definition.active and enabled
                updated = ProductionExtension(definition.extension_point, definition.provider_id, enabled, definition.metadata, active)
                self._extensions[key] = (updated, factory); updated_items.append(updated)
                if definition.active and not enabled: self._active.pop(extension_point, None)
            return sorted(updated_items, key=lambda item:item.provider_id)[0]

    def has(self, extension_point: str, provider_id: str | None = None) -> bool:
        with self._lock:
            return any(key[0] == extension_point and (provider_id is None or key[1] == provider_id) for key in self._extensions)

    def get(self, extension_point: str, provider_id: str | None = None) -> ProductionExtension:
        with self._lock:
            return self._entry(extension_point, provider_id)[0]

    def activate(self, extension_point: str, provider_id: str) -> ProductionExtension:
        with self._lock:
            definition, _ = self._entry(extension_point, provider_id)
            if not definition.enabled: raise ProductionExtensionError(f"extension provider is disabled: {extension_point}/{provider_id}")
            self._activate_locked(extension_point, provider_id)
            return self._extensions[(extension_point, provider_id)][0]

    def create(self, extension_point: str, /, *, provider_id: str | None = None, **configuration: Any) -> Any:
        with self._lock:
            definition, factory = self._entry(extension_point, provider_id)
        if not definition.enabled:
            raise ProductionExtensionError(f"extension is disabled: {extension_point}")
        instance = factory(**configuration)
        if instance is None:
            raise ProductionExtensionError(f"extension returned no instance: {extension_point}")
        return instance

    def list(self) -> tuple[ProductionExtension, ...]:
        with self._lock:
            return tuple(sorted((value[0] for value in self._extensions.values()), key=lambda item:(item.extension_point, not item.active, item.provider_id)))

    def _entry(self, extension_point: str, provider_id: str | None = None) -> tuple[ProductionExtension, ExtensionFactory]:
        provider = provider_id or self._active.get(extension_point)
        if not provider:
            raise ProductionExtensionError(f"extension has no active provider: {extension_point}")
        try:
            return self._extensions[(extension_point, provider)]
        except KeyError as error:
            raise ProductionExtensionError(f"extension provider is not installed: {extension_point}/{provider}") from error

    def _activate_locked(self, extension_point: str, provider_id: str) -> None:
        for key, (definition, factory) in tuple(self._extensions.items()):
            if key[0] != extension_point: continue
            self._extensions[key] = (ProductionExtension(definition.extension_point, definition.provider_id, definition.enabled, definition.metadata, key[1] == provider_id), factory)
        self._active[extension_point] = provider_id


_DEFAULT_REGISTRY = ProductionExtensionRegistry()


def production_extension_registry() -> ProductionExtensionRegistry:
    return _DEFAULT_REGISTRY
