from __future__ import annotations

import importlib.util
from io import BytesIO
from pathlib import Path
import sys
import unittest
from zipfile import ZipFile


PATH = Path(__file__).resolve().parents[2] / "plugins/builtin/short_drama/workflows/delivery_pipeline.py"
SPEC = importlib.util.spec_from_file_location("short_drama_delivery_pipeline", PATH)
MODULE = importlib.util.module_from_spec(SPEC); assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE; SPEC.loader.exec_module(MODULE)


class Provider:
    def compose(self, inputs): return MODULE.DeliveryOutput(b"real-composed-video", "video/mp4")
    def review(self, content, media_type): return MODULE.ReviewDecision(True, ())
    def repair(self, content, media_type, issues): return MODULE.DeliveryOutput(b"repaired", media_type)


class DeliveryPipelineTest(unittest.TestCase):
    def test_compose_review_and_export_real_bytes(self) -> None:
        pipeline = MODULE.DeliveryPipeline(Provider())
        composition = pipeline.composition([b"video"], [b"audio"], [b"subtitle"])
        exported = pipeline.export(composition, pipeline.confirm_review(pipeline.review(composition)))
        self.assertEqual(exported.node_type, "review_export")
        with ZipFile(BytesIO(exported.content)) as archive:
            self.assertEqual(archive.read("final.mp4"), b"real-composed-video")

    def test_rejected_review_cannot_export(self) -> None:
        pipeline = MODULE.DeliveryPipeline(Provider())
        composition = pipeline.composition([b"v"], [b"a"], [b"s"])
        with self.assertRaisesRegex(MODULE.DeliveryPipelineError, "cannot be exported"):
            pipeline.export(composition, MODULE.ReviewDecision(False, ("quality",)))

    def test_rejected_review_can_be_repaired_then_reconfirmed(self) -> None:
        pipeline=MODULE.DeliveryPipeline(Provider());composition=pipeline.composition([b"v"],[b"a"],[b"s"]);repaired=pipeline.repair(composition,MODULE.ReviewDecision(False,("quality",)));self.assertEqual(repaired.content,b"repaired")

    def test_missing_inputs_are_rejected(self) -> None:
        with self.assertRaisesRegex(MODULE.DeliveryPipelineError, "requires"):
            MODULE.DeliveryPipeline(Provider()).composition([], [b"a"], [b"s"])


if __name__ == "__main__": unittest.main()
