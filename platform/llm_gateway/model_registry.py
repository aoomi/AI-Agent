"""Register real model endpoints and select models by declared capabilities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Iterable, Mapping


MODEL_CAPABILITIES = frozenset(
    {"chat", "reasoning", "tool_calling", "vision", "structured_output"}
)


class ModelRegistryError(ValueError):
    """Raised when a model definition or selection is invalid."""


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    model_id: str
    provider_id: str
    display_name: str
    capabilities: frozenset[str]
    enabled: bool
    context_window: int
    settings: Mapping[str, Any]
    contract_version: str = "1.0"

    @classmethod
    def create(
        cls,
        *,
        model_id: str,
        provider_id: str,
        display_name: str,
        capabilities: Iterable[str],
        enabled: bool = True,
        context_window: int,
        settings: Mapping[str, Any] | None = None,
    ) -> "ModelDefinition":
        normalized = frozenset(capabilities)
        values = {
            "model_id": model_id.strip(),
            "provider_id": provider_id.strip(),
            "display_name": display_name.strip(),
        }
        if not all(values.values()):
            raise ModelRegistryError("model_id, provider_id and display_name are required")
        unknown = normalized - MODEL_CAPABILITIES
        if not normalized or unknown:
            raise ModelRegistryError(f"invalid model capabilities: {sorted(unknown)}")
        if context_window < 1:
            raise ModelRegistryError("context_window must be positive")
        return cls(
            **values,
            capabilities=normalized,
            enabled=enabled,
            context_window=context_window,
            settings=MappingProxyType(dict(settings or {})),
        )


@dataclass(frozen=True, slots=True)
class ModelRequirements:
    capabilities: frozenset[str]
    minimum_context_window: int = 1
    provider_id: str | None = None

    def __post_init__(self) -> None:
        unknown = self.capabilities - MODEL_CAPABILITIES
        if unknown:
            raise ModelRegistryError(f"invalid required capabilities: {sorted(unknown)}")
        if self.minimum_context_window < 1:
            raise ModelRegistryError("minimum_context_window must be positive")


class ModelRegistry:
    """In-memory source of truth for deployer-provided model definitions."""

    def __init__(self) -> None:
        self._models: dict[str, ModelDefinition] = {}

    def register(self, model: ModelDefinition) -> tuple[ModelDefinition, bool]:
        existing = self._models.get(model.model_id)
        if existing is not None:
            if existing != model:
                raise ModelRegistryError(f"conflicting model_id: {model.model_id}")
            return existing, True
        self._models[model.model_id] = model
        return model, False

    def get(self, model_id: str, *, require_enabled: bool = False) -> ModelDefinition:
        try:
            model = self._models[model_id]
        except KeyError as error:
            raise ModelRegistryError(f"unknown model_id: {model_id}") from error
        if require_enabled and not model.enabled:
            raise ModelRegistryError(f"model is disabled: {model_id}")
        return model

    def set_enabled(self, model_id: str, enabled: bool) -> ModelDefinition:
        updated = replace(self.get(model_id), enabled=enabled)
        self._models[model_id] = updated
        return updated

    def list(self, *, enabled_only: bool = False) -> tuple[ModelDefinition, ...]:
        models = self._models.values()
        if enabled_only:
            models = (model for model in models if model.enabled)
        return tuple(sorted(models, key=lambda model: model.model_id))

    def select(
        self,
        requirements: ModelRequirements,
        *,
        preferred_model_id: str | None = None,
    ) -> ModelDefinition:
        candidates = [
            model
            for model in self._models.values()
            if model.enabled
            and requirements.capabilities <= model.capabilities
            and model.context_window >= requirements.minimum_context_window
            and (requirements.provider_id is None or model.provider_id == requirements.provider_id)
        ]
        if preferred_model_id is not None:
            preferred = next(
                (model for model in candidates if model.model_id == preferred_model_id), None
            )
            if preferred is None:
                raise ModelRegistryError(
                    f"preferred model does not satisfy requirements: {preferred_model_id}"
                )
            return preferred
        if not candidates:
            raise ModelRegistryError("no enabled model satisfies requirements")
        return min(candidates, key=lambda model: (model.context_window, model.model_id))
