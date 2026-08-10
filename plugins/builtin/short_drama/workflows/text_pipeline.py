"""Requirements, outline, script and storyboard nodes for the short-drama plugin."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping, Protocol


class TextPipelineError(ValueError):
    """Raised when text input or provider output cannot form a real artifact."""


class TextGenerationProvider(Protocol):
    def generate(self, capability: str, inputs: Mapping[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class TextArtifact:
    node_type: str
    content: Mapping[str, Any]
    checksum_sha256: str
    media_type: str = "application/json"


def _artifact(node_type: str, content: Mapping[str, Any]) -> TextArtifact:
    if not content:
        raise TextPipelineError(f"{node_type} output must not be empty")
    normalized = json.loads(json.dumps(dict(content), ensure_ascii=False))
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return TextArtifact(node_type, MappingProxyType(normalized), sha256(encoded).hexdigest())


class TextPipeline:
    def __init__(self, provider: TextGenerationProvider) -> None:
        self.provider = provider

    def requirements(self, brief: Mapping[str, Any]) -> TextArtifact:
        required = ("title", "premise", "episode_count")
        if any(key not in brief for key in required):
            raise TextPipelineError("requirements need title, premise and episode_count")
        if not isinstance(brief["episode_count"], int) or brief["episode_count"] < 1:
            raise TextPipelineError("episode_count must be a positive integer")
        if not str(brief["title"]).strip() or not str(brief["premise"]).strip():
            raise TextPipelineError("title and premise must not be empty")
        return _artifact("requirements", brief)

    def outline(self, requirements: TextArtifact) -> TextArtifact:
        self._require_node(requirements, "requirements")
        output = self.provider.generate("short_drama.outline", requirements.content)
        if not isinstance(output.get("episodes"), list) or not output["episodes"]:
            raise TextPipelineError("outline provider must return non-empty episodes")
        return _artifact("outline", output)

    def script(self, outline: TextArtifact) -> TextArtifact:
        self._require_node(outline, "outline")
        output = self.provider.generate("short_drama.script", outline.content)
        if not isinstance(output.get("scenes"), list) or not output["scenes"]:
            raise TextPipelineError("script provider must return non-empty scenes")
        return _artifact("script", output)

    def storyboard(self, script: TextArtifact) -> TextArtifact:
        self._require_node(script, "script")
        output = self.provider.generate("short_drama.storyboard", script.content)
        if not isinstance(output.get("shots"), list) or not output["shots"]:
            raise TextPipelineError("storyboard provider must return non-empty shots")
        return _artifact("storyboard", output)

    def asset_catalog(self, storyboard: TextArtifact) -> TextArtifact:
        self._require_node(storyboard, "storyboard")
        output = self.provider.generate("short_drama.asset_catalog", storyboard.content)
        for key in ("characters", "scenes", "props", "shot_prompts"):
            if not isinstance(output.get(key), list): raise TextPipelineError(f"asset catalog requires {key}")
        return _artifact("assets", output)

    def run_preproduction(self, brief: Mapping[str, Any]) -> tuple[TextArtifact, ...]:
        requirements=self.requirements(brief);outline=self.outline(requirements);script=self.script(outline);storyboard=self.storyboard(script);assets=self.asset_catalog(storyboard)
        return requirements,outline,script,storyboard,assets

    @staticmethod
    def _require_node(artifact: TextArtifact, expected: str) -> None:
        if artifact.node_type != expected:
            raise TextPipelineError(f"expected {expected} artifact")
