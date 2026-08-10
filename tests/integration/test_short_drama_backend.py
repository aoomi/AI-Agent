from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from ai_agent_tenant import IdentityContext
from ai_agent_events import EventBus
from ai_agent_queue import InMemoryTaskQueue, TaskService
from short_drama_backend import ShortDramaBackend, ShortDramaProviders
from short_drama_workflows.delivery_pipeline import DeliveryOutput, ReviewDecision
from short_drama_workflows.media_pipeline import ProviderOutput


class TextProvider:
    def generate(self, capability, inputs):
        if capability.endswith("outline"): return {"episodes": [{"episode": 1, "summary": inputs["premise"]}]}
        if capability.endswith("script"): return {"scenes": [{"scene": 1, "dialogue": "provider-script"}]}
        return {"shots": [{"shot": 1, "description": inputs["scenes"][0]["dialogue"]}]}


class MediaProvider:
    def generate(self, capability, inputs):
        media = {"assets": "application/json", "image": "image/png", "video": "video/mp4", "audio": "audio/wav", "subtitle": "text/vtt"}[capability.rsplit(".", 1)[-1]]
        return [ProviderOutput((capability + "-provider-output").encode(), media, "source-1")]


class DeliveryProviderImpl:
    def compose(self, inputs): return DeliveryOutput(b"provider-composed-video", "video/mp4")
    def review(self, content, media_type): return ReviewDecision(True, ())


class ShortDramaBackendTest(unittest.TestCase):
    def test_public_entry_runs_real_provider_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backend = ShortDramaBackend(Path(directory), ShortDramaProviders(TextProvider(), MediaProvider(), DeliveryProviderImpl()))
            context = IdentityContext("request-1", "trace-1", "identity-1", "user", "tenant-a")
            waiting = backend.start(context, "project-a", "operation-1", {"title": "Title", "premise": "Premise", "episode_count": 1})
            self.assertEqual(waiting.status, "waiting_human")
            completed = waiting
            while completed.status == "waiting_human":
                completed = backend.approve(context, "project-a", waiting.run_id)
            exported = Path(directory) / completed.artifacts["review_export"]
            with ZipFile(BytesIO(exported.read_bytes())) as archive:
                self.assertEqual(archive.read("final.mp4"), b"provider-composed-video")

    def test_pipeline_task_is_visible_to_shared_task_service(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue, events = InMemoryTaskQueue(), EventBus()
            service = TaskService(queue, events)
            backend = ShortDramaBackend(Path(directory), ShortDramaProviders(TextProvider(), MediaProvider(), DeliveryProviderImpl()), queue, events)
            context = IdentityContext("request-1", "trace-1", "identity-1", "user", "tenant-a")
            waiting = backend.start(context, "project-a", "operation-1", {"title": "Title", "premise": "Premise", "episode_count": 1})
            task = service.get_task(context, waiting.task_id)
            self.assertEqual(task.status, "waiting_human")
            self.assertEqual(task.payload["progress_percent"], 9)
            current = waiting
            while current.status == "waiting_human":
                current = backend.approve(context, "project-a", waiting.run_id)
            self.assertEqual(service.get_task(context, waiting.task_id).status, "completed")


if __name__ == "__main__": unittest.main()
