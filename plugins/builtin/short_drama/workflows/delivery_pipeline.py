"""Composition, review and export nodes for real generated media."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import Any, Mapping, Protocol, Sequence
from zipfile import ZIP_DEFLATED, ZipFile


class DeliveryPipelineError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DeliveryOutput:
    content: bytes
    media_type: str


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    approved: bool
    issues: tuple[str, ...]
    confirmed: bool = False


class DeliveryProvider(Protocol):
    def compose(self, inputs: Mapping[str, Sequence[bytes]]) -> DeliveryOutput: ...
    def review(self, content: bytes, media_type: str) -> ReviewDecision: ...
    def repair(self, content: bytes, media_type: str, issues: tuple[str, ...]) -> DeliveryOutput: ...


@dataclass(frozen=True, slots=True)
class DeliveryArtifact:
    node_type: str
    content: bytes
    media_type: str
    checksum_sha256: str


class DeliveryPipeline:
    def __init__(self, provider: DeliveryProvider) -> None:
        self.provider = provider

    def composition(self, videos: Sequence[bytes], audio: Sequence[bytes], subtitles: Sequence[bytes]) -> DeliveryArtifact:
        if not videos or not audio or not subtitles:
            raise DeliveryPipelineError("composition requires video, audio and subtitle inputs")
        output = self.provider.compose({"videos": videos, "audio": audio, "subtitles": subtitles})
        return self._artifact("composition", output)

    def review(self, composition: DeliveryArtifact) -> ReviewDecision:
        if composition.node_type != "composition" or not composition.content:
            raise DeliveryPipelineError("review requires composition artifact")
        decision = self.provider.review(composition.content, composition.media_type)
        if decision.approved and decision.issues:
            raise DeliveryPipelineError("approved review cannot contain issues")
        if not decision.approved and not decision.issues:
            raise DeliveryPipelineError("rejected review must contain issues")
        return decision

    @staticmethod
    def confirm_review(decision: ReviewDecision) -> ReviewDecision:
        if not decision.approved or decision.issues: raise DeliveryPipelineError("only approved review can be confirmed")
        return ReviewDecision(True, (), True)

    def repair(self, composition: DeliveryArtifact, decision: ReviewDecision) -> DeliveryArtifact:
        if decision.approved or not decision.issues: raise DeliveryPipelineError("repair requires rejected review issues")
        return self._artifact("composition", self.provider.repair(composition.content, composition.media_type, decision.issues))

    def export(self, composition: DeliveryArtifact, decision: ReviewDecision) -> DeliveryArtifact:
        if not decision.approved or not decision.confirmed:
            raise DeliveryPipelineError("composition cannot be exported without confirmed approval")
        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("final.mp4", composition.content)
            archive.writestr("manifest.json", b'{"status":"approved","contract_version":"1.0"}')
        return self._artifact("review_export", DeliveryOutput(buffer.getvalue(), "application/zip"))

    @staticmethod
    def _artifact(node: str, output: DeliveryOutput) -> DeliveryArtifact:
        if not output.content or not output.media_type.strip():
            raise DeliveryPipelineError(f"{node} provider returned invalid output")
        return DeliveryArtifact(node, output.content, output.media_type, sha256(output.content).hexdigest())
