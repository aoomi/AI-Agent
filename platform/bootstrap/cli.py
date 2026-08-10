"""Console entry point for the platform API process."""

from __future__ import annotations

from ai_agent_core import PlatformConfig

from .application import create_server


def main() -> None:
    config = PlatformConfig.from_environment()
    server = create_server(config)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
