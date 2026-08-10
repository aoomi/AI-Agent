from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


PATH = Path(__file__).resolve().parents[2] / "plugins/builtin/short_drama/workflows/media_pipeline.py"
SPEC = importlib.util.spec_from_file_location("short_drama_media_pipeline", PATH)
MODULE = importlib.util.module_from_spec(SPEC); assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE; SPEC.loader.exec_module(MODULE)


class Provider:
    def generate(self, capability, inputs):
        media = {"assets": "application/json", "image": "image/png", "video": "video/mp4", "audio": "audio/wav", "subtitle": "text/vtt"}[capability.rsplit(".", 1)[-1]]
        return [MODULE.ProviderOutput((capability + ":real-output").encode(), media, "source-1")]


class MediaPipelineTest(unittest.TestCase):
    def test_five_media_nodes_produce_nonempty_hashed_outputs(self) -> None:
        pipeline = MODULE.MediaPipeline(Provider())
        assets = pipeline.assets({"shots": [{"shot": 1}]})
        images = pipeline.images(assets); videos = pipeline.videos(images)
        audio = pipeline.audio(videos); subtitles = pipeline.subtitles(audio)
        self.assertEqual([assets.node_type, images.node_type, videos.node_type, audio.node_type, subtitles.node_type], ["assets", "image", "video", "audio", "subtitle"])
        self.assertTrue(all(len(item.checksum_sha256) == 64 for artifact in (assets, images, videos, audio, subtitles) for item in artifact.items))

    def test_empty_provider_output_is_rejected(self) -> None:
        class Empty:
            def generate(self, capability, inputs): return []
        with self.assertRaises(MODULE.MediaPipelineError):
            MODULE.MediaPipeline(Empty()).assets({"shots": []})

    def test_wrong_upstream_node_is_rejected(self) -> None:
        artifact = MODULE.MediaArtifact("video", (MODULE.MediaItem("x", b"x", "video/mp4", "a" * 64),))
        with self.assertRaisesRegex(MODULE.MediaPipelineError, "requires"):
            MODULE.MediaPipeline(Provider()).images(artifact)

    def test_local_regeneration_versions_selected_shot(self) -> None:
        pipeline=MODULE.MediaPipeline(Provider());artifact=pipeline.assets({"shots":[1]});updated=pipeline.regenerate(artifact,("source-1",),"short_drama.assets")
        self.assertEqual(updated.revision,2);self.assertEqual(updated.items[0].version,2)

    def test_audio_timeline_validation(self) -> None:
        one=MODULE.MediaItem("a",b"a","audio/wav","a"*64,"voice",1,0,100);two=MODULE.MediaItem("b",b"b","audio/wav","b"*64,"effect",1,100,200);MODULE.MediaPipeline.validate_timeline(MODULE.MediaArtifact("audio",(one,two)))
        with self.assertRaisesRegex(MODULE.MediaPipelineError,"overlap"):MODULE.MediaPipeline.validate_timeline(MODULE.MediaArtifact("audio",(one,MODULE.MediaItem("b",b"b","audio/wav","b"*64,"effect",1,50,200))))


if __name__ == "__main__": unittest.main()
