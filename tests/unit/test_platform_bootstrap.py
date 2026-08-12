from __future__ import annotations

import json
import os
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import patch

from ai_agent_bootstrap.application import create_server
from ai_agent_core import PlatformConfig


class PlatformConfigTest(unittest.TestCase):
    def test_direct_configuration_rejects_invalid_runtime_values(self) -> None:
        for kwargs in ({"host":" "},{"host":1},{"environment":" "},{"environment":1},{"port":True},{"port":65536}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                PlatformConfig(**kwargs)

    def test_environment_configuration_is_validated(self) -> None:
        environment = {
            "AI_AGENT_HOST": "127.0.0.1",
            "AI_AGENT_PORT": "9000",
            "AI_AGENT_ENVIRONMENT": "test",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(
                PlatformConfig.from_environment(),
                PlatformConfig(host="127.0.0.1", port=9000, environment="test"),
            )

    def test_invalid_port_is_rejected(self) -> None:
        with patch.dict(os.environ, {"AI_AGENT_PORT": "0"}, clear=True):
            with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
                PlatformConfig.from_environment()


class PlatformHealthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = create_server(
            PlatformConfig(host="127.0.0.1", port=0, environment="test")
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_endpoint(self) -> None:
        host, port = self.server.server_address
        with urlopen(f"http://{host}:{port}/health", timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(
                json.load(response)["data"],
                {
                    "status": "healthy",
                    "service": "ai-agent-platform",
                    "environment": "test",
                },
            )

    def test_unknown_path_is_not_found(self) -> None:
        host, port = self.server.server_address
        with self.assertRaises(HTTPError) as context:
            urlopen(f"http://{host}:{port}/unknown", timeout=2)
        self.assertEqual(context.exception.code, 404)
        payload = json.load(context.exception)
        self.assertEqual(payload["code"], 404)
        self.assertEqual(payload["data"]["error_code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
