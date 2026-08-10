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
from ai_agent_events import EventBus, PublishedEvent
from ai_agent_queue import InMemoryTaskQueue, QueuedTask
from ai_agent_tenant import IdentityContext


class TaskTrackingApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.queue = InMemoryTaskQueue()
        self.events = EventBus()
        context = IdentityContext("request-seed", "trace-seed", "identity-1", "user", "tenant-a")
        self.queue.enqueue(QueuedTask("task-a", "project-a", "operation-a", "pipeline", context, {}))
        self.queue.enqueue(QueuedTask("task-b", "project-b", "operation-b", "pipeline", context, {}))
        other = IdentityContext("request-seed", "trace-seed", "identity-2", "user", "tenant-b")
        self.queue.enqueue(QueuedTask("task-c", "project-a", "operation-c", "pipeline", other, {}))
        recoverable = IdentityContext("request-seed", "trace-seed", "identity-3", "user", "tenant-c")
        self.queue.enqueue(QueuedTask("task-d", "project-c", "operation-d", "pipeline", recoverable, {}))
        self.queue.claim("tenant-c"); self.queue.finish("task-d", "failed")
        temp = tempfile.TemporaryDirectory(); self.temp = temp
        self.server = create_server(PlatformConfig(port=0, environment="test"), Path(temp.name), self.queue, self.events)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.base = f"http://{self.server.server_address[0]}:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2); self.temp.cleanup()

    @staticmethod
    def headers(tenant="tenant-a"):
        return {"X-Request-Id": "request-1", "X-Trace-Id": "trace-1", "X-Identity-Id": "identity-1", "X-Identity-Kind": "user", "X-Tenant-Id": tenant}

    def test_list_detail_cancel_and_cross_tenant_isolation(self) -> None:
        request = Request(self.base + "/api/v1/tasks?project_id=project-a", headers=self.headers())
        with urlopen(request, timeout=2) as response: items = json.load(response)["data"]["items"]
        self.assertEqual([item["task_id"] for item in items], ["task-a"])
        with urlopen(Request(self.base + "/api/v1/tasks/task-a", headers=self.headers()), timeout=2) as response:
            self.assertEqual(json.load(response)["data"]["status"], "queued")
        cancel = Request(self.base + "/api/v1/tasks/task-a/cancel", headers=self.headers(), data=b"", method="POST")
        with urlopen(cancel, timeout=2) as response: self.assertEqual(json.load(response)["data"]["status"], "cancelled")
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base + "/api/v1/tasks/task-a", headers=self.headers("tenant-b")), timeout=2)
        self.assertEqual(error.exception.code, 404)

    def test_status_event_is_visible_on_next_refresh(self) -> None:
        event_context = IdentityContext("request-event", "trace-event", "identity-1", "user", "tenant-a")
        self.events.publish(PublishedEvent("event-1", "TASK_STATUS_CHANGED", "project-a", event_context, {"task_id": "task-a", "current_status": "running", "progress_percent": 40}))
        request = Request(self.base + "/api/v1/tasks/task-a", headers=self.headers())
        with urlopen(request, timeout=2) as response: task = json.load(response)["data"]
        self.assertEqual(task["status"], "running")
        self.assertEqual(task["payload"]["progress_percent"], 40)

    def test_failed_task_can_resume_through_http(self) -> None:
        resume = Request(self.base + "/api/v1/tasks/task-d/resume", headers=self.headers("tenant-c"), data=b"", method="POST")
        with urlopen(resume, timeout=2) as response:
            self.assertEqual(json.load(response)["data"]["status"], "queued")


if __name__ == "__main__": unittest.main()
