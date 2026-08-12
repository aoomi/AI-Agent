"""Replaceable infrastructure extension points for the production kernel."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import Any, Callable, Mapping
import json


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


@dataclass(frozen=True, slots=True)
class _ProviderContract:
    implementation_type: type
    required_methods: tuple[str, ...]
    probe_configuration: Mapping[str, Any]
    trusted_builtin: bool = False


class ProductionExtensionRegistry:
    """Keeps the production kernel independent from storage and runtime implementations."""

    def __init__(self, *, trusted_builtin_providers: set[tuple[str, str]] | None = None) -> None:
        if trusted_builtin_providers is not None and (not isinstance(trusted_builtin_providers,set) or any(not isinstance(item,tuple) or len(item)!=2 or any(not isinstance(value,str) or not value.strip() for value in item) for item in trusted_builtin_providers)):raise ProductionExtensionError("trusted builtin provider set is invalid")
        self._lock = RLock()
        self._extensions: dict[tuple[str, str], tuple[ProductionExtension, ExtensionFactory]] = {}
        self._active: dict[str, str] = {}
        self._contracts: dict[tuple[str, str], _ProviderContract] = {}
        self._point_required_methods: dict[str, tuple[str, ...]] = {}
        self._inflight: dict[tuple[str, str], int] = {}
        # Trust is granted by the application composition root, never by
        # provider-controlled metadata. A plugin cannot obtain the builtin
        # probe exemption by setting metadata["builtin"] itself.
        self._trusted_builtin_providers = frozenset(trusted_builtin_providers or set())

    @staticmethod
    def _contains_sensitive_key(value: Any) -> bool:
        forbidden = ("secret", "token", "password", "api_key", "authorization", "credential")
        if isinstance(value, Mapping):
            return any(
                any(word in str(key).lower() for word in forbidden)
                or ProductionExtensionRegistry._contains_sensitive_key(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple, set, frozenset)):
            return any(ProductionExtensionRegistry._contains_sensitive_key(item) for item in value)
        return False

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
        if not isinstance(extension_point,str) or not isinstance(provider_id,str):raise ProductionExtensionError("extension point, provider and factory are required")
        point, provider = extension_point.strip(), provider_id.strip()
        if not point or not provider or not callable(factory):
            raise ProductionExtensionError("extension point, provider and factory are required")
        if (not isinstance(enabled,bool) or not isinstance(replace,bool) or not isinstance(replace_provider,bool)
                or activate is not None and not isinstance(activate,bool)):raise ProductionExtensionError("extension control flags must be boolean")
        if metadata is not None and not isinstance(metadata,Mapping):raise ProductionExtensionError("extension metadata must be a mapping")
        metadata_values = dict(metadata or {})
        if self._contains_sensitive_key(metadata_values):
            raise ProductionExtensionError("extension metadata contain sensitive fields")
        required_value = metadata_values.get("required_methods", ())
        if "required_methods" in metadata_values and not isinstance(required_value, (list, tuple, set)):
            raise ProductionExtensionError(f"invalid required_methods contract: {point}/{provider}")
        if any(not isinstance(name,str) or not name.strip() for name in required_value):raise ProductionExtensionError(f"invalid required_methods contract: {point}/{provider}")
        serializable_metadata={key:value for key,value in metadata_values.items() if key!="implementation_type"}
        try:canonical_metadata=json.dumps(serializable_metadata,allow_nan=False)
        except (TypeError,ValueError) as error:raise ProductionExtensionError("extension metadata must be standard JSON") from error
        metadata_snapshot=json.loads(canonical_metadata)
        required = tuple(dict.fromkeys(name.strip() for name in required_value))
        with self._lock:
            point_required = self._point_required_methods.get(point, ())
        if point_required and not required:
            raise ProductionExtensionError(f"extension point contract is required: {point}/{provider}")
        missing_point_methods = sorted(set(point_required).difference(required))
        if missing_point_methods:
            raise ProductionExtensionError(
                f"extension point contract mismatch: {point}/{provider}; missing methods: {','.join(missing_point_methods)}"
            )
        contract: _ProviderContract | None = None
        if required:
            implementation_type = metadata_values.pop("implementation_type", None)
            if not isinstance(implementation_type, type):
                raise ProductionExtensionError(
                    f"extension provider contract type is required: {point}/{provider}"
                )
            missing = sorted(name for name in required if not callable(getattr(implementation_type, name, None)))
            if missing:
                raise ProductionExtensionError(
                    f"extension provider contract mismatch: {point}/{provider}; missing methods: {','.join(missing)}"
                )
            metadata_values["implementation_type"] = f"{implementation_type.__module__}.{implementation_type.__qualname__}"
            metadata_values["required_methods"] = list(required)
            metadata_values["contract_validated"] = True
            probe_configuration = metadata_values.pop("probe_configuration", {})
            if not isinstance(probe_configuration, Mapping):
                raise ProductionExtensionError(f"invalid provider probe configuration: {point}/{provider}")
            probe_snapshot = json.loads(json.dumps(dict(probe_configuration), allow_nan=False))
            contract = _ProviderContract(
                implementation_type=implementation_type,
                required_methods=required,
                probe_configuration=MappingProxyType(probe_snapshot),
                trusted_builtin=(point, provider) in self._trusted_builtin_providers,
            )
            self._probe_factory(point, provider, factory, contract)
        key = (point, provider)
        with self._lock:
            # Recheck the point-level schema inside the mutation lock: two
            # providers may have completed their expensive probes concurrently.
            current_point_required = self._point_required_methods.get(point, ())
            if current_point_required and contract is None:
                raise ProductionExtensionError(f"extension point contract is required: {point}/{provider}")
            concurrent_missing = sorted(set(current_point_required).difference(required))
            if concurrent_missing:
                raise ProductionExtensionError(
                    f"extension point contract mismatch: {point}/{provider}; missing methods: {','.join(concurrent_missing)}"
                )
            if not current_point_required and contract is not None and not replace:
                legacy = [item_key for item_key in self._extensions if item_key[0] == point and item_key not in self._contracts]
                if legacy:
                    raise ProductionExtensionError(
                        f"extension point has uncontracted providers; complete replacement is required: {point}"
                    )
            was_active = self._active.get(point) == provider
            should_activate = activate if activate is not None else was_active or replace or point not in self._active
            # Validate the complete replacement before mutating the registry.  A
            # rejected replacement must never destroy the currently active
            # infrastructure binding.
            if should_activate and not enabled:
                raise ProductionExtensionError("disabled extension provider cannot be activated")
            if replace and any(count for item_key, count in self._inflight.items() if item_key[0] == point):
                raise ProductionExtensionError(f"extension point has in-flight creations: {point}")
            if replace_provider and self._inflight.get(key, 0):
                raise ProductionExtensionError(f"extension provider has in-flight creations: {point}/{provider}")
            if replace:
                self._extensions = {item_key:item for item_key, item in self._extensions.items() if item_key[0] != point}
                self._contracts = {item_key:item for item_key, item in self._contracts.items() if item_key[0] != point}
                self._active.pop(point, None)
            elif key in self._extensions and not replace_provider:
                raise ProductionExtensionError(f"extension provider already registered: {point}/{provider}")
            for metadata_key, value in metadata_snapshot.items():
                if metadata_key not in {"implementation_type", "probe_configuration"}:
                    metadata_values[metadata_key] = value
            definition = ProductionExtension(point, provider, enabled, MappingProxyType(metadata_values), should_activate)
            self._extensions[key] = (definition, factory)
            if contract is None:
                self._contracts.pop(key, None)
            else:
                self._contracts[key] = contract
                if point not in self._point_required_methods:
                    self._point_required_methods[point] = required
            if should_activate:
                self._activate_locked(point, provider)
            elif self._active.get(point) == provider:
                self._active.pop(point, None)
        return definition

    def unregister(self, extension_point: str, provider_id: str | None = None) -> bool:
        extension_point = self._required_id("extension point", extension_point)
        provider_id = self._optional_id("provider", provider_id)
        candidate_snapshot: tuple[str, ProductionExtension, ExtensionFactory, _ProviderContract | None] | None = None
        with self._lock:
            targets = [key for key in self._extensions if key[0] == extension_point and (provider_id is None or key[1] == provider_id)]
            active_creations = [key for key in targets if self._inflight.get(key, 0)]
            if active_creations:
                raise ProductionExtensionError(
                    f"extension provider has in-flight creations: {active_creations[0][0]}/{active_creations[0][1]}"
                )
            was_active = self._active.get(extension_point) in {key[1] for key in targets}
            if was_active:
                candidates = sorted(
                    (key[1], entry[0], entry[1], self._contracts.get(key))
                    for key, entry in self._extensions.items()
                    if key[0] == extension_point and key not in targets and entry[0].enabled
                )
                if candidates:
                    candidate_snapshot = candidates[0]
        if candidate_snapshot is not None:
            candidate_provider, _, candidate_factory, candidate_contract = candidate_snapshot
            if candidate_contract is not None:
                self._probe_factory(extension_point, candidate_provider, candidate_factory, candidate_contract)
        with self._lock:
            targets = [key for key in self._extensions if key[0] == extension_point and (provider_id is None or key[1] == provider_id)]
            active_creations = [key for key in targets if self._inflight.get(key, 0)]
            if active_creations:
                raise ProductionExtensionError(
                    f"extension provider has in-flight creations: {active_creations[0][0]}/{active_creations[0][1]}"
                )
            was_active = self._active.get(extension_point) in {key[1] for key in targets}
            if candidate_snapshot is not None:
                candidate_provider, candidate_definition, candidate_factory, candidate_contract = candidate_snapshot
                current = self._extensions.get((extension_point, candidate_provider))
                if current != (candidate_definition, candidate_factory) or self._contracts.get((extension_point, candidate_provider)) is not candidate_contract:
                    raise ProductionExtensionError(f"extension provider changed during unregister: {extension_point}/{candidate_provider}")
            for key in targets:
                del self._extensions[key]
                self._contracts.pop(key, None)
            if was_active:
                self._active.pop(extension_point, None)
                if candidate_snapshot is not None:
                    self._activate_locked(extension_point, candidate_snapshot[0])
            return bool(targets)

    def enable(self, extension_point: str, enabled: bool, provider_id: str | None = None) -> ProductionExtension:
        extension_point = self._required_id("extension point", extension_point)
        provider_id = self._optional_id("provider", provider_id)
        if not isinstance(enabled, bool):
            raise ProductionExtensionError("enabled must be boolean")
        with self._lock:
            targets = [key for key in self._extensions if key[0] == extension_point and (provider_id is None or key[1] == provider_id)]
            if not targets: raise ProductionExtensionError(f"extension is not installed: {extension_point}")
            if not enabled:
                active_creations = [key for key in targets if self._inflight.get(key, 0)]
                if active_creations:
                    raise ProductionExtensionError(
                        f"extension provider has in-flight creations: {active_creations[0][0]}/{active_creations[0][1]}"
                    )
            updated_items = []
            for key in targets:
                definition, factory = self._extensions[key]
                active = definition.active and enabled
                updated = ProductionExtension(definition.extension_point, definition.provider_id, enabled, definition.metadata, active)
                self._extensions[key] = (updated, factory); updated_items.append(updated)
                if definition.active and not enabled: self._active.pop(extension_point, None)
            return sorted(updated_items, key=lambda item:item.provider_id)[0]

    def has(self, extension_point: str, provider_id: str | None = None) -> bool:
        extension_point = self._required_id("extension point", extension_point)
        provider_id = self._optional_id("provider", provider_id)
        with self._lock:
            return any(key[0] == extension_point and (provider_id is None or key[1] == provider_id) for key in self._extensions)

    def get(self, extension_point: str, provider_id: str | None = None) -> ProductionExtension:
        extension_point = self._required_id("extension point", extension_point)
        provider_id = self._optional_id("provider", provider_id)
        with self._lock:
            return self._entry(extension_point, provider_id)[0]

    def activate(self, extension_point: str, provider_id: str) -> ProductionExtension:
        extension_point = self._required_id("extension point", extension_point)
        provider_id = self._required_id("provider", provider_id)
        with self._lock:
            active_provider = self._active.get(extension_point)
            if active_provider and active_provider != provider_id and self._inflight.get((extension_point, active_provider), 0):
                raise ProductionExtensionError(
                    f"extension provider has in-flight creations: {extension_point}/{active_provider}"
                )
            definition, factory = self._entry(extension_point, provider_id)
            if not definition.enabled: raise ProductionExtensionError(f"extension provider is disabled: {extension_point}/{provider_id}")
            contract = self._contracts.get((extension_point, provider_id))
            if self._point_required_methods.get(extension_point) and contract is None:
                raise ProductionExtensionError(f"extension point contract is required: {extension_point}/{provider_id}")
        if contract is not None:
            self._probe_factory(extension_point, provider_id, factory, contract)
        with self._lock:
            current_definition, current_factory = self._entry(extension_point, provider_id)
            if current_factory is not factory or self._contracts.get((extension_point, provider_id)) is not contract:
                raise ProductionExtensionError(f"extension provider changed during activation: {extension_point}/{provider_id}")
            if not current_definition.enabled:
                raise ProductionExtensionError(f"extension provider is disabled: {extension_point}/{provider_id}")
            self._activate_locked(extension_point, provider_id)
            return self._extensions[(extension_point, provider_id)][0]

    def create(self, extension_point: str, /, *, provider_id: str | None = None, **configuration: Any) -> Any:
        extension_point = self._required_id("extension point", extension_point)
        provider_id = self._optional_id("provider", provider_id)
        try:configuration_snapshot=json.loads(json.dumps(configuration,allow_nan=False))
        except (TypeError,ValueError) as error:raise ProductionExtensionError("extension configuration must be standard JSON") from error
        with self._lock:
            definition, factory = self._entry(extension_point, provider_id)
            contract = self._contracts.get((extension_point, definition.provider_id))
            if not definition.enabled:
                raise ProductionExtensionError(f"extension is disabled: {extension_point}")
            key = (extension_point, definition.provider_id)
            self._inflight[key] = self._inflight.get(key, 0) + 1
        try:
            instance = factory(**configuration_snapshot)
            if instance is None:
                raise ProductionExtensionError(f"extension returned no instance: {extension_point}")
            if contract is not None:
                self._validate_instance(extension_point, definition.provider_id, instance, contract)
            return instance
        finally:
            with self._lock:
                remaining = self._inflight.get(key, 1) - 1
                if remaining:
                    self._inflight[key] = remaining
                else:
                    self._inflight.pop(key, None)

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

    @staticmethod
    def _required_id(field_name: str, value: str) -> str:
        if not isinstance(value,str):raise ProductionExtensionError(f"{field_name} is required")
        normalized = value.strip()
        if not normalized:
            raise ProductionExtensionError(f"{field_name} is required")
        return normalized

    @classmethod
    def _optional_id(cls, field_name: str, value: str | None) -> str | None:
        return None if value is None else cls._required_id(field_name, value)

    def _activate_locked(self, extension_point: str, provider_id: str) -> None:
        for key, (definition, factory) in tuple(self._extensions.items()):
            if key[0] != extension_point: continue
            self._extensions[key] = (ProductionExtension(definition.extension_point, definition.provider_id, definition.enabled, definition.metadata, key[1] == provider_id), factory)
        self._active[extension_point] = provider_id

    @classmethod
    def _probe_factory(
        cls,
        extension_point: str,
        provider_id: str,
        factory: ExtensionFactory,
        contract: _ProviderContract,
    ) -> None:
        # Builtins require live runtime objects (database paths, schedulers,
        # graph stores) and are class-checked during installation, then
        # instance-checked by create(). Third-party providers must pass a real
        # factory probe before every registry mutation that can activate them.
        if contract.trusted_builtin:
            return
        candidate: Any = None
        try:
            candidate = factory(**dict(contract.probe_configuration))
            if candidate is None:
                raise ProductionExtensionError(f"extension returned no instance: {extension_point}/{provider_id}")
            cls._validate_instance(extension_point, provider_id, candidate, contract)
        except ProductionExtensionError:
            raise
        except Exception as error:
            raise ProductionExtensionError(
                f"extension provider contract probe failed: {extension_point}/{provider_id}: {error}"
            ) from error
        finally:
            close = getattr(candidate, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    @staticmethod
    def _validate_instance(
        extension_point: str,
        provider_id: str,
        instance: Any,
        contract: _ProviderContract,
    ) -> None:
        if not isinstance(instance, contract.implementation_type):
            raise ProductionExtensionError(
                f"extension provider implementation type mismatch: {extension_point}/{provider_id}"
            )
        missing = sorted(name for name in contract.required_methods if not callable(getattr(instance, name, None)))
        if missing:
            raise ProductionExtensionError(
                f"extension provider contract mismatch: {extension_point}/{provider_id}; "
                f"missing methods: {','.join(missing)}"
            )


_TRUSTED_BUILTIN_PROVIDERS = {
    ("resource.scheduler", "builtin.pooled_priority_resource_scheduler"),
    ("storage.production_ledger", "builtin.sqlite_production_ledger"),
    ("storage.story_bible", "builtin.sqlite_story_bible"),
    ("storage.task_repository", "builtin.sqlite_task_repository"),
    ("checkpoint.langgraph", "builtin.langgraph_sqlite"),
    ("routing.workload", "builtin.health_aware_workload_router"),
    ("storage.task_lease", "builtin.sqlite_task_lease"),
    ("discovery.workers", "builtin.sqlite_worker_registry"),
}


_DEFAULT_REGISTRY = ProductionExtensionRegistry(trusted_builtin_providers=_TRUSTED_BUILTIN_PROVIDERS)


def production_extension_registry() -> ProductionExtensionRegistry:
    return _DEFAULT_REGISTRY
