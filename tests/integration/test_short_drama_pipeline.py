from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ai_agent_events import EventBus
from ai_agent_queue import InMemoryTaskQueue
from ai_agent_tenant import IdentityContext
from short_drama_workflows.pipeline import NODES, NodeOutput, ShortDramaPipeline, ShortDramaPipelineError


class ShortDramaPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.context = IdentityContext("request-1", "trace-1", "identity-1", "user", "tenant-a")
        self.events = EventBus(); self.received = []
        self.events.subscribe("ASSET_STATUS_CHANGED", self.received.append)
        self.queue = InMemoryTaskQueue()
        self.runners = {node: self.runner(node) for node in NODES}
        self.pipeline = ShortDramaPipeline(Path(self.temp.name), self.queue, self.events, self.runners)

    def tearDown(self) -> None: self.temp.cleanup()

    @staticmethod
    def runner(node):
        return lambda artifacts: NodeOutput((node + ":" + str(len(artifacts))).encode(), "application/octet-stream")

    def test_full_flow_requires_human_then_exports_and_recovers(self) -> None:
        waiting = self.pipeline.start(self.context, "project-a", "operation-1")
        self.assertEqual(waiting.status, "waiting_human")
        self.assertEqual(waiting.next_index, 1)
        restarted = ShortDramaPipeline(Path(self.temp.name), self.queue, self.events, self.runners)
        restored = restarted.load(self.context, "project-a", waiting.run_id)
        self.assertEqual(restored.artifacts.keys(), {"requirements"})
        completed = restored
        while completed.status == "waiting_human":
            completed = restarted.approve(self.context, "project-a", waiting.run_id)
        self.assertEqual(completed.status, "completed")
        self.assertEqual(set(completed.artifacts), set(NODES))
        self.assertEqual(len(self.received), 11)
        self.assertTrue(all((Path(self.temp.name) / value).is_file() for value in completed.artifacts.values()))

    def test_waiting_run_can_be_cancelled(self) -> None:
        waiting = self.pipeline.start(self.context, "project-a", "operation-2")
        self.assertEqual(self.pipeline.cancel(self.context, "project-a", waiting.run_id).status, "cancelled")
        restarted = ShortDramaPipeline(Path(self.temp.name), self.queue, self.events, self.runners)
        restored = restarted.load(self.context, "project-a", waiting.run_id)
        self.assertEqual(restored.status, "cancelled")
        self.assertEqual(restarted.orchestrator.state(restarted._identity(restored))["status"], "cancelled")
        with self.assertRaisesRegex(ShortDramaPipelineError, "only waiting_human"):
            restarted.approve(self.context, "project-a", waiting.run_id)
        with self.assertRaisesRegex(ShortDramaPipelineError, "only running"):
            restarted.resume(self.context, "project-a", waiting.run_id)
        with self.assertRaisesRegex(ValueError, "workflow is cancelled"):
            restarted.orchestrator.execute(restarted._identity(restored), "requirements", {"artifacts":{}})

    def test_cross_tenant_checkpoint_read_is_rejected(self) -> None:
        waiting = self.pipeline.start(self.context, "project-a", "operation-3")
        with self.assertRaises(ShortDramaPipelineError):
            self.pipeline.load(IdentityContext("request-2", "trace-2", "identity-1", "user", "tenant-b"), "project-a", waiting.run_id)

    def test_cross_identity_checkpoint_read_and_mutation_are_rejected(self) -> None:
        waiting = self.pipeline.start(self.context, "project-a", "operation-identity")
        other = IdentityContext("request-2", "trace-2", "identity-2", "user", "tenant-a")
        for operation in (
            lambda: self.pipeline.load(other, "project-a", waiting.run_id),
            lambda: self.pipeline.approve(other, "project-a", waiting.run_id),
            lambda: self.pipeline.cancel(other, "project-a", waiting.run_id),
        ):
            with self.assertRaisesRegex(ShortDramaPipelineError, "not owned"):
                operation()

    def test_node_failure_is_persisted_and_not_reported_as_success(self) -> None:
        runners = dict(self.runners)
        runners["image"] = lambda artifacts: (_ for _ in ()).throw(RuntimeError("provider failed"))
        pipeline = ShortDramaPipeline(Path(self.temp.name), self.queue, self.events, runners)
        waiting = pipeline.start(self.context, "project-a", "operation-4")
        with self.assertRaisesRegex(ShortDramaPipelineError, "provider failed"):
            while waiting.status == "waiting_human":
                waiting = pipeline.approve(self.context, "project-a", waiting.run_id)
        checkpoints = list((Path(self.temp.name) / "tenant-a/project-a/checkpoints").glob("*.json"))
        self.assertEqual(len(checkpoints), 1)
        import json
        self.assertEqual(json.loads(checkpoints[0].read_text())["status"], "failed")

    def test_checkpoint_rejects_tampered_scope_lifecycle_and_artifacts(self) -> None:
        waiting=self.pipeline.start(self.context,"project-a","operation-tamper")
        path=Path(self.temp.name)/"tenant-a/project-a/checkpoints"/f"{waiting.run_id}.json"
        import json
        original=json.loads(path.read_text())
        mutations=(
            {**original,"tenant_id":"tenant-b"},
            {**original,"run_id":"run-forged"},
            {**original,"status":"unknown"},
            {**original,"next_index":True},
            {**original,"artifacts":{"unknown":"artifact.bin"}},
        )
        for payload in mutations:
            path.write_text(json.dumps(payload),encoding="utf-8")
            with self.subTest(payload=payload),self.assertRaises(ShortDramaPipelineError):
                self.pipeline.load(self.context,"project-a",waiting.run_id)

    def test_stage_boundaries_reject_pseudo_outputs_and_artifact_keys(self) -> None:
        with self.assertRaisesRegex(ShortDramaPipelineError,"initial requirements"):
            self.pipeline.start(self.context,"project-a","bad-initial",object())
        for inputs in ({"artifacts":{1:"path"}},{"artifacts":{"unknown":"path"}},{"artifacts":{"image":1}}):
            with self.subTest(inputs=inputs),self.assertRaisesRegex(ShortDramaPipelineError,"artifacts are invalid"):
                self.pipeline._execute_stage("video",inputs)
        self.pipeline.runners["video"]=lambda _:object()
        with self.assertRaisesRegex(ShortDramaPipelineError,"invalid output"):
            self.pipeline._execute_stage("video",{"artifacts":{"image":"image.bin"}})


if __name__ == "__main__": unittest.main()
