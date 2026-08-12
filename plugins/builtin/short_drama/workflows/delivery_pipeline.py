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
        inputs = (videos, audio, subtitles)
        if any(isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence) or not values or any(not isinstance(value, bytes) or not value for value in values) for values in inputs):
            raise DeliveryPipelineError("composition requires video, audio and subtitle inputs")
        output = self.provider.compose({"videos": videos, "audio": audio, "subtitles": subtitles})
        return self._artifact("composition", output)

    def review(self, composition: DeliveryArtifact) -> ReviewDecision:
        if not self._valid_composition(composition):
            raise DeliveryPipelineError("review requires composition artifact")
        decision = self.provider.review(composition.content, composition.media_type)
        if not isinstance(decision,ReviewDecision) or not isinstance(decision.approved,bool) or not isinstance(decision.confirmed,bool) or not isinstance(decision.issues,tuple) or any(not isinstance(issue,str) or not issue.strip() for issue in decision.issues):
            raise DeliveryPipelineError("review provider returned invalid decision")
        if decision.approved and decision.issues:
            raise DeliveryPipelineError("approved review cannot contain issues")
        if not decision.approved and not decision.issues:
            raise DeliveryPipelineError("rejected review must contain issues")
        return decision

    @staticmethod
    def confirm_review(decision: ReviewDecision) -> ReviewDecision:
        if not DeliveryPipeline._valid_decision(decision) or not decision.approved or decision.issues: raise DeliveryPipelineError("only approved review can be confirmed")
        return ReviewDecision(True, (), True)

    def repair(self, composition: DeliveryArtifact, decision: ReviewDecision) -> DeliveryArtifact:
        if not self._valid_composition(composition): raise DeliveryPipelineError("repair requires composition artifact")
        if not self._valid_decision(decision) or decision.approved or not decision.issues: raise DeliveryPipelineError("repair requires rejected review issues")
        return self._artifact("composition", self.provider.repair(composition.content, composition.media_type, decision.issues))

    def export(self, composition: DeliveryArtifact, decision: ReviewDecision) -> DeliveryArtifact:
        if not self._valid_composition(composition): raise DeliveryPipelineError("export requires composition artifact")
        if not self._valid_decision(decision) or not decision.approved or not decision.confirmed:
            raise DeliveryPipelineError("composition cannot be exported without confirmed approval")
        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("final.mp4", composition.content)
            archive.writestr("manifest.json", b'{"status":"approved","contract_version":"1.0"}')
        return self._artifact("review_export", DeliveryOutput(buffer.getvalue(), "application/zip"))

    @staticmethod
    def _artifact(node: str, output: DeliveryOutput) -> DeliveryArtifact:
        if not isinstance(output,DeliveryOutput) or not isinstance(output.content,bytes) or not isinstance(output.media_type,str) or not output.content or not output.media_type.strip():
            raise DeliveryPipelineError(f"{node} provider returned invalid output")
        return DeliveryArtifact(node, output.content, output.media_type, sha256(output.content).hexdigest())

    @staticmethod
    def _valid_composition(value: object) -> bool:
        return isinstance(value, DeliveryArtifact) and value.node_type == "composition" and isinstance(value.content, bytes) and bool(value.content) and isinstance(value.media_type, str) and bool(value.media_type.strip()) and isinstance(value.checksum_sha256, str) and value.checksum_sha256 == sha256(value.content).hexdigest()

    @staticmethod
    def _valid_decision(value: object) -> bool:
        return isinstance(value, ReviewDecision) and isinstance(value.approved, bool) and isinstance(value.confirmed, bool) and isinstance(value.issues, tuple) and all(isinstance(issue, str) and bool(issue.strip()) for issue in value.issues) and not (value.approved and value.issues) and not (not value.approved and not value.issues)
