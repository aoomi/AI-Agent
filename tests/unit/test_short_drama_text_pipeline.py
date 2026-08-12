from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "plugins/builtin/short_drama/workflows/text_pipeline.py"
SPEC = importlib.util.spec_from_file_location("short_drama_text_pipeline", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class Provider:
    def generate(self, capability, inputs):
        if capability.endswith("outline"):
            return {"episodes": [{"episode": 1, "summary": inputs["premise"]}]}
        if capability.endswith("script"):
            return {"scenes": [{"scene": 1, "dialogue": "真实输入生成内容"}]}
        return {"shots": [{"shot": 1, "description": inputs["scenes"][0]["dialogue"]}]}


class TextPipelineTest(unittest.TestCase):
    def test_artifact_rejects_non_standard_json(self):
        for invalid in (float("nan"), object()):
            with self.assertRaisesRegex(MODULE.TextPipelineError, "standard JSON"):
                MODULE._artifact("outline", {"episodes": [{"value": invalid}]})

    def test_four_text_nodes_produce_hashed_structured_artifacts(self) -> None:
        pipeline = MODULE.TextPipeline(Provider())
        requirements = pipeline.requirements({"title": "项目", "premise": "冲突", "episode_count": 1})
        outline = pipeline.outline(requirements)
        script = pipeline.script(outline)
        storyboard = pipeline.storyboard(script)
        self.assertEqual([requirements.node_type, outline.node_type, script.node_type, storyboard.node_type], ["requirements", "outline", "script", "storyboard"])
        self.assertEqual(len(storyboard.checksum_sha256), 64)

    def test_invalid_requirements_are_rejected(self) -> None:
        with self.assertRaisesRegex(MODULE.TextPipelineError, "requirements need"):
            MODULE.TextPipeline(Provider()).requirements({"title": "missing"})

    def test_empty_provider_output_is_rejected(self) -> None:
        class EmptyProvider:
            def generate(self, capability, inputs): return {}
        pipeline = MODULE.TextPipeline(EmptyProvider())
        requirements = pipeline.requirements({"title": "项目", "premise": "冲突", "episode_count": 1})
        with self.assertRaises(MODULE.TextPipelineError):
            pipeline.outline(requirements)

    def test_real_preproduction_chain_includes_asset_catalog(self) -> None:
        class ChainProvider:
            def generate(self, capability, inputs):
                if capability.endswith("outline"): return {"episodes":[1]}
                if capability.endswith("script"): return {"scenes":[1]}
                if capability.endswith("storyboard"): return {"shots":[1]}
                return {"characters":[],"scenes":[],"props":[],"shot_prompts":[]}
        artifacts=MODULE.TextPipeline(ChainProvider()).run_preproduction({"title":"剧","premise":"故事","episode_count":1})
        self.assertEqual(tuple(item.node_type for item in artifacts),("requirements","outline","script","storyboard","assets"))


if __name__ == "__main__": unittest.main()
