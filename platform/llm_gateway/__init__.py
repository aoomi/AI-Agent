"""Registered model discovery and capability-safe selection."""

from .model_registry import (
    ModelDefinition,
    ModelRegistry,
    ModelRegistryError,
    ModelRequirements,
)
from .openai_client import (OpenAIClientCancelled, OpenAIClientError, OpenAIClientTimeout,
    OpenAICompatibleClient, OpenAIResponseError, OpenAITransportResponse, UrllibOpenAITransport)

__all__ = [
    "ModelDefinition",
    "ModelRegistry",
    "ModelRegistryError",
    "ModelRequirements",
    "OpenAIClientCancelled", "OpenAIClientError", "OpenAIClientTimeout", "OpenAICompatibleClient",
    "OpenAIResponseError", "OpenAITransportResponse", "UrllibOpenAITransport",
]
