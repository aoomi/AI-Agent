"""Public backend entry that wires real providers into the short-drama workflow."""

from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from ai_agent_events import EventBus
from ai_agent_queue import InMemoryTaskQueue
from ai_agent_tenant import IdentityContext
from short_drama_workflows.delivery_pipeline import DeliveryPipeline, DeliveryProvider
from short_drama_workflows.media_pipeline import MediaArtifact, MediaGenerationProvider, MediaItem, MediaPipeline
from short_drama_workflows.pipeline import NODES, NodeOutput, PipelineCheckpoint, ShortDramaPipeline
from short_drama_workflows.text_pipeline import TextArtifact, TextGenerationProvider, TextPipeline


PLUGIN_ID = "short_drama"


@dataclass(frozen=True, slots=True)
class ShortDramaProviders:
    text: TextGenerationProvider
    media: MediaGenerationProvider
    delivery: DeliveryProvider


class ShortDramaBackend:
    def __init__(self, data_root: Path, providers: ShortDramaProviders, queue: InMemoryTaskQueue | None = None, events: EventBus | None = None) -> None:
        self.root = data_root.resolve()
        self.text = TextPipeline(providers.text)
        self.media = MediaPipeline(providers.media)
        self.delivery = DeliveryPipeline(providers.delivery)
        self.queue = queue or InMemoryTaskQueue()
        self.events = events or EventBus()
        self.pipeline = ShortDramaPipeline(self.root, self.queue, self.events, self._runners())

    def start(self, context: IdentityContext, project_id: str, operation_key: str, brief: Mapping[str, Any]) -> PipelineCheckpoint:
        requirements = self.text.requirements(brief)
        initial = NodeOutput(self._json_bytes(requirements.content), requirements.media_type)
        return self.pipeline.start(context, project_id, operation_key, initial)

    def approve(self, context: IdentityContext, project_id: str, run_id: str) -> PipelineCheckpoint:
        return self.pipeline.approve(context, project_id, run_id)

    def cancel(self, context: IdentityContext, project_id: str, run_id: str) -> PipelineCheckpoint:
        return self.pipeline.cancel(context, project_id, run_id)

    def status(self, context: IdentityContext, project_id: str, run_id: str) -> PipelineCheckpoint:
        return self.pipeline.load(context.tenant_id, project_id, run_id)

    def _runners(self):
        return {
            "requirements": lambda _: (_ for _ in ()).throw(RuntimeError("requirements are supplied at start")),
            "outline": lambda paths: self._text_output(self.text.outline(self._read_text(paths, "requirements", "requirements"))),
            "script": lambda paths: self._text_output(self.text.script(self._read_text(paths, "outline", "outline"))),
            "storyboard": lambda paths: self._text_output(self.text.storyboard(self._read_text(paths, "script", "script"))),
            "assets": lambda paths: self._media_output(self.media.assets(self._read_json(paths, "storyboard"))),
            "image": lambda paths: self._media_output(self.media.images(self._read_media(paths, "assets"))),
            "video": lambda paths: self._media_output(self.media.videos(self._read_media(paths, "image"))),
            "audio": lambda paths: self._media_output(self.media.audio(self._read_media(paths, "video"))),
            "subtitle": lambda paths: self._media_output(self.media.subtitles(self._read_media(paths, "audio"))),
            "composition": self._composition,
            "review_export": self._review_export,
        }

    def _composition(self, paths: Mapping[str, str]) -> NodeOutput:
        videos = [item.content for item in self._read_media(paths, "video").items]
        audio = [item.content for item in self._read_media(paths, "audio").items]
        subtitles = [item.content for item in self._read_media(paths, "subtitle").items]
        artifact = self.delivery.composition(videos, audio, subtitles)
        return NodeOutput(artifact.content, artifact.media_type)

    def _review_export(self, paths: Mapping[str, str]) -> NodeOutput:
        content = self._read_bytes(paths, "composition")
        from short_drama_workflows.delivery_pipeline import DeliveryArtifact
        composition = DeliveryArtifact("composition", content, "video/mp4", "")
        exported = self.delivery.export(composition, self.delivery.confirm_review(self.delivery.review(composition)))
        return NodeOutput(exported.content, exported.media_type)

    def _read_text(self, paths: Mapping[str, str], key: str, node: str) -> TextArtifact:
        return TextArtifact(node, self._read_json(paths, key), "")

    def _read_media(self, paths: Mapping[str, str], key: str) -> MediaArtifact:
        data = self._read_json(paths, key)
        items = tuple(MediaItem(item["source_id"], b64decode(item["content"]), item["media_type"], item["checksum_sha256"]) for item in data["items"])
        return MediaArtifact(key, items)

    def _read_json(self, paths: Mapping[str, str], key: str) -> Mapping[str, Any]:
        return json.loads(self._read_bytes(paths, key))

    def _read_bytes(self, paths: Mapping[str, str], key: str) -> bytes:
        return (self.root / paths[key]).read_bytes()

    @classmethod
    def _text_output(cls, artifact: TextArtifact) -> NodeOutput:
        return NodeOutput(cls._json_bytes(artifact.content), artifact.media_type)

    @classmethod
    def _media_output(cls, artifact: MediaArtifact) -> NodeOutput:
        data = {"items": [{"source_id": item.source_id, "content": b64encode(item.content).decode("ascii"), "media_type": item.media_type, "checksum_sha256": item.checksum_sha256} for item in artifact.items]}
        return NodeOutput(cls._json_bytes(data), "application/json")

    @staticmethod
    def _json_bytes(value: Mapping[str, Any]) -> bytes:
        return json.dumps(dict(value), ensure_ascii=False, sort_keys=True).encode("utf-8")


def plugin_identity() -> dict[str, str]:
    return {"plugin_id": PLUGIN_ID, "version": "1.0.0"}
