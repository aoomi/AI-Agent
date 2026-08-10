"""Platform bootstrap and health-check entry points."""

from .application import create_server

__all__ = ["create_server"]
