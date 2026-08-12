from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_agent_core import WorkerRegistry, WorkloadRouter, WorkloadRoutingError


class WorkerNumericContractTest(unittest.TestCase):
    def test_router_rejects_pseudo_numeric_controls(self) -> None:
        for kwargs in ({"heartbeat_timeout": True}, {"max_queue_depth": 1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                WorkloadRouter(**kwargs)  # type: ignore[arg-type]
        router = WorkloadRouter()
        with self.assertRaisesRegex(WorkloadRoutingError, "invalid worker route"):
            router.route("video", estimated_memory=True)  # type: ignore[arg-type]

    def test_registry_rejects_pseudo_numeric_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = WorkerRegistry(Path(directory) / "workers.db")
            for operation in (
                lambda: registry.list(heartbeat_timeout=True),
                lambda: registry.reap(heartbeat_timeout=True),
                lambda: registry.reserve("request", "video", estimated_memory=True),
                lambda: registry.reserve("request", "video", reservation_ttl=True),
            ):
                with self.subTest(operation=operation), self.assertRaises(WorkloadRoutingError):
                    operation()


if __name__ == "__main__":
    unittest.main()
