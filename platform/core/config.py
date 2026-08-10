"""Environment-backed configuration for the platform process."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _read_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise ValueError("AI_AGENT_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("AI_AGENT_PORT must be between 1 and 65535")
    return port


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """Validated process configuration with safe local defaults."""

    host: str = "127.0.0.1"
    port: int = 8080
    environment: str = "development"

    @classmethod
    def from_environment(cls) -> "PlatformConfig":
        host = os.environ.get("AI_AGENT_HOST", "127.0.0.1").strip()
        environment = os.environ.get("AI_AGENT_ENVIRONMENT", "development").strip()
        if not host:
            raise ValueError("AI_AGENT_HOST must not be empty")
        if not environment:
            raise ValueError("AI_AGENT_ENVIRONMENT must not be empty")
        return cls(
            host=host,
            port=_read_port(os.environ.get("AI_AGENT_PORT", "8080")),
            environment=environment,
        )
