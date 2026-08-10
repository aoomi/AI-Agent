from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen

from ai_agent_bootstrap.application import create_server
from ai_agent_core import PlatformConfig


class AgentApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / "builtin/short_drama/skills/writer"
        root.mkdir(parents=True)
        (root / "main.py").write_text("def run(): pass\n", encoding="utf-8")
        (root / "manifest.yaml").write_text(
            "skill_id: short_drama.writer\nname: Writer\nversion: 1.0.0\nentry_point: main.py\n", encoding="utf-8"
        )
        self.server = create_server(PlatformConfig(port=0, environment="test"), Path(self.temp.name) / "builtin")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://{self.server.server_address[0]}:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2); self.temp.cleanup()

    def test_register_and_query_agent(self) -> None:
        headers = {"Content-Type": "application/json", "X-Request-Id": "request-1", "X-Trace-Id": "trace-1", "X-Identity-Id": "identity-1", "X-Identity-Kind": "user", "X-Tenant-Id": "tenant-a"}
        request = Request(self.base + "/api/v1/agents/register", data=json.dumps({"skill_id": "short_drama.writer"}).encode(), headers=headers, method="POST")
        with urlopen(request, timeout=2) as response:
            agent = json.load(response)["data"]
        self.assertEqual(agent["name"], "Writer")
        with urlopen(Request(self.base + "/api/v1/agents/" + agent["agent_id"], headers=headers), timeout=2) as response:
            self.assertEqual(json.load(response)["data"]["status"], "idle")


if __name__ == "__main__": unittest.main()
