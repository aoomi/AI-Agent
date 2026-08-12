from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ai_agent_bootstrap.application import create_server
from ai_agent_core import PlatformConfig


class ModelClient:
    def complete(self, model, messages, response_schema):
        return {"reply": "请确认复杂任务", "proposal": {"proposal_type": "task_execution", "requested_changes": {"objective": "实现功能"}}}


class TaskExecutor:
    def execute(self, configuration, requested_changes, confirmed_by_identity_id):
        return {"task_id": "task-complex-1"}


class AgentManagementApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.server = create_server(
            PlatformConfig(port=0, environment="test"),
            Path(__file__).resolve().parents[2] / "plugins/builtin",
            conversation_model_client=ModelClient(), task_proposal_executor=TaskExecutor(),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.base = f"http://{self.server.server_address[0]}:{self.server.server_address[1]}"
        self.headers = {"Content-Type": "application/json", "X-Request-Id": "request-1", "X-Trace-Id": "trace-1", "X-Identity-Id": "identity-1", "X-Identity-Kind": "user", "X-Tenant-Id": "tenant-a"}

    def tearDown(self) -> None:
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2); self.temp.cleanup()

    def post(self, path, body):
        request = Request(self.base + path, data=json.dumps(body).encode(), headers=self.headers, method="POST")
        with urlopen(request, timeout=2) as response: return json.load(response)["data"]

    def get(self, path):
        with urlopen(Request(self.base + path, headers=self.headers), timeout=2) as response: return json.load(response)["data"]

    def test_model_configuration_conversation_and_task_confirmation(self) -> None:
        agent = self.post("/api/v1/agents/register", {"skill_id": "system_main_developer"})
        model = self.post("/api/v1/models/register", {"model_id": "model-full", "provider_id": "provider", "display_name": "Full", "capabilities": ["chat", "reasoning", "tool_calling", "structured_output"], "context_window": 32768})
        self.assertFalse(model["replayed"]); self.assertEqual(len(self.get("/api/v1/models")["items"]), 1)
        configuration = self.post("/api/v1/agent-configurations", {"agent_id": agent["agent_id"], "model_id": "model-full"})
        self.assertTrue(configuration["writable"])
        updated = self.post(f"/api/v1/agent-configurations/{agent['agent_id']}/update", {"expected_version": 1, "settings": {"approval": "strict"}})
        self.assertEqual(updated["configuration_version"], 2)
        self.assertEqual(len(self.get(f"/api/v1/agent-configurations/{agent['agent_id']}/history")["items"]), 2)
        session = self.post("/api/v1/agent-conversations", {"agent_id": agent["agent_id"], "context":{"project_id":"project"}})
        turn = self.post(f"/api/v1/agent-conversations/{session['session_id']}/messages", {"content": "执行复杂任务"})
        self.assertEqual(turn["proposal"]["status"], "pending_confirmation")
        applied = self.post(f"/api/v1/agent-proposals/{turn['proposal']['proposal_id']}/confirm", {})
        self.assertEqual(applied["applied_result"]["task_id"], "task-complex-1")
        self.assertEqual(len(self.get(f"/api/v1/agent-conversations/{session['session_id']}")["messages"]), 3)

    def test_project_skill_selection_registers_reusable_robot(self) -> None:
        skills = self.get("/api/v1/industry-skills")["items"]
        self.assertIn("duanju.fenjing_huamian", {item["skill_id"] for item in skills})
        first = self.post("/api/v1/industry-robots/register", {"skill_id": "duanju.fenjing_huamian", "project_id": "project-1"})
        second = self.post("/api/v1/industry-robots/register", {"skill_id": "duanju.fenjing_huamian", "project_id": "project-1"})
        self.assertEqual(first["robot_id"], second["robot_id"])
        self.assertEqual(first["project_id"], "project-1")

    def test_unconfigured_real_model_client_fails_explicitly(self) -> None:
        server = create_server(PlatformConfig(port=0, environment="test"), Path(__file__).resolve().parents[2] / "plugins/builtin")
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            base = f"http://{server.server_address[0]}:{server.server_address[1]}"
            def post(path, body):
                request = Request(base + path, data=json.dumps(body).encode(), headers=self.headers, method="POST")
                with urlopen(request, timeout=2) as response: return json.load(response)["data"]
            agent = post("/api/v1/agents/register", {"skill_id": "system_main_developer"})
            post("/api/v1/models/register", {"model_id": "model-full", "provider_id": "provider", "display_name": "Full", "capabilities": ["chat", "reasoning", "tool_calling", "structured_output"], "context_window": 32768})
            post("/api/v1/agent-configurations", {"agent_id": agent["agent_id"], "model_id": "model-full"})
            session = post("/api/v1/agent-conversations", {"agent_id": agent["agent_id"], "context":{"project_id":"project"}})
            with self.assertRaises(HTTPError) as error: post(f"/api/v1/agent-conversations/{session['session_id']}/messages", {"content": "你好"})
            self.assertEqual(error.exception.code, 409)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)


if __name__ == "__main__": unittest.main()
