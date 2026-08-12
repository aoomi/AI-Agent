"""Asset, image, video, audio and subtitle generation nodes."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Protocol, Sequence


class MediaPipelineError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderOutput:
    content: bytes
    media_type: str
    source_id: str
    asset_kind: str = "shot"
    start_ms: int = 0
    end_ms: int = 1


class MediaGenerationProvider(Protocol):
    def generate(self, capability: str, inputs: Mapping[str, Any]) -> Sequence[ProviderOutput]: ...


@dataclass(frozen=True, slots=True)
class MediaItem:
    source_id: str
    content: bytes
    media_type: str
    checksum_sha256: str
    asset_kind: str = "shot"
    version: int = 1
    start_ms: int = 0
    end_ms: int = 1


@dataclass(frozen=True, slots=True)
class MediaArtifact:
    node_type: str
    items: tuple[MediaItem, ...]
    revision: int = 1


class MediaPipeline:
    def __init__(self, provider: MediaGenerationProvider) -> None:
        self.provider = provider

    def assets(self, storyboard: Mapping[str, Any]) -> MediaArtifact:
        return self._generate("assets", "short_drama.assets", storyboard)

    def images(self, assets: MediaArtifact) -> MediaArtifact:
        return self._from_artifact("image", "short_drama.image", assets, "assets")

    def videos(self, images: MediaArtifact) -> MediaArtifact:
        return self._from_artifact("video", "short_drama.video", images, "image")

    def image_to_video(self, images: MediaArtifact) -> MediaArtifact:
        return self._from_artifact("video", "short_drama.image_to_video", images, "image")

    def text_to_video(self, shot_prompts: Mapping[str, Any]) -> MediaArtifact:
        return self._generate("video", "short_drama.text_to_video", shot_prompts)

    def audio(self, videos: MediaArtifact) -> MediaArtifact:
        return self._from_artifact("audio", "short_drama.audio", videos, "video")

    def subtitles(self, audio: MediaArtifact) -> MediaArtifact:
        return self._from_artifact("subtitle", "short_drama.subtitle", audio, "audio")

    def regenerate(self, artifact: MediaArtifact, source_ids: tuple[str, ...], capability: str) -> MediaArtifact:
        if not isinstance(artifact,MediaArtifact) or not artifact.items or any(not isinstance(item,MediaItem) for item in artifact.items): raise MediaPipelineError("regeneration requires media artifact")
        if not isinstance(source_ids,tuple) or not source_ids or any(not isinstance(source_id,str) or not source_id.strip() for source_id in source_ids) or len(source_ids)!=len(set(source_ids)): raise MediaPipelineError("regeneration source ids are invalid")
        if not isinstance(capability,str) or not capability.strip(): raise MediaPipelineError("regeneration capability is invalid")
        selected=[item for item in artifact.items if item.source_id in source_ids]
        if len(selected)!=len(source_ids): raise MediaPipelineError("regeneration source ids are invalid")
        generated=self._generate(artifact.node_type,capability,{"items":[{"source_id":item.source_id,"version":item.version,"checksum_sha256":item.checksum_sha256} for item in selected]})
        replacements={item.source_id:item for item in generated.items}
        merged=tuple(replacements.get(item.source_id,item) if item.source_id not in replacements else MediaItem(replacements[item.source_id].source_id,replacements[item.source_id].content,replacements[item.source_id].media_type,replacements[item.source_id].checksum_sha256,replacements[item.source_id].asset_kind,item.version+1,replacements[item.source_id].start_ms,replacements[item.source_id].end_ms) for item in artifact.items)
        return MediaArtifact(artifact.node_type,merged,artifact.revision+1)

    @staticmethod
    def validate_timeline(artifact: MediaArtifact) -> None:
        if not isinstance(artifact,MediaArtifact) or artifact.node_type not in {"audio","subtitle"}: raise MediaPipelineError("timeline validation requires audio or subtitle artifact")
        if any(not isinstance(item,MediaItem) for item in artifact.items): raise MediaPipelineError("timeline item is invalid")
        if any(any(isinstance(value,bool) or not isinstance(value,int) for value in (item.start_ms,item.end_ms)) or item.start_ms<0 or item.end_ms<=item.start_ms for item in artifact.items): raise MediaPipelineError("timeline item range is invalid")
        ordered=sorted(artifact.items,key=lambda item:item.start_ms)
        if any(left.end_ms>right.start_ms for left,right in zip(ordered,ordered[1:])): raise MediaPipelineError("timeline items overlap")

    def _from_artifact(self, node: str, capability: str, upstream: MediaArtifact, expected: str) -> MediaArtifact:
        if not isinstance(upstream,MediaArtifact) or upstream.node_type != expected or not upstream.items or any(not isinstance(item,MediaItem) for item in upstream.items):
            raise MediaPipelineError(f"{node} requires non-empty {expected} artifact")
        inputs = {"items": [{"source_id": item.source_id, "media_type": item.media_type, "checksum_sha256": item.checksum_sha256} for item in upstream.items]}
        return self._generate(node, capability, inputs)

    def _generate(self, node: str, capability: str, inputs: Mapping[str, Any]) -> MediaArtifact:
        outputs = self.provider.generate(capability, inputs)
        if isinstance(outputs,(str,bytes,bytearray)) or not isinstance(outputs,Sequence) or not outputs:
            raise MediaPipelineError(f"{node} provider returned no output")
        items = []
        for output in outputs:
            if not isinstance(output,ProviderOutput) or not isinstance(output.content,bytes) or not isinstance(output.media_type,str) or not isinstance(output.source_id,str) or not isinstance(output.asset_kind,str):
                raise MediaPipelineError(f"{node} provider returned invalid output")
            if not output.content or not output.media_type.strip() or not output.source_id.strip() or not output.asset_kind.strip():
                raise MediaPipelineError(f"{node} provider returned invalid output")
            if any(isinstance(value,bool) or not isinstance(value,int) for value in (output.start_ms,output.end_ms)) or output.start_ms < 0 or output.end_ms <= output.start_ms: raise MediaPipelineError(f"{node} provider returned invalid timeline")
            items.append(MediaItem(output.source_id, output.content, output.media_type, sha256(output.content).hexdigest(), output.asset_kind, 1, output.start_ms, output.end_ms))
        return MediaArtifact(node, tuple(items))
