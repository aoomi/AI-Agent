from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).parents[2] / "plugins/builtin/short_drama/backend/compat_server.py"
SPEC = importlib.util.spec_from_file_location("short_drama_compat_validation", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_shots(count: int = 15, duration: int = 60) -> list[dict]:
    shots = []
    start = 0.0
    for index in range(count):
        end = duration if index == count - 1 else round(duration * (index + 1) / count, 3)
        shots.append({
            "start_second": start,
            "end_second": end,
            "scene": "室内",
            "shot_size": "近景",
            "camera": "固定机位",
            "visual": f"人物完成剧情动作{index + 1}",
            "action": f"动作{index + 1}",
            "dialogue": "",
            "sound": "环境音",
            "image_prompt": f"完整画面{index + 1}",
        })
        start = end
    return shots


class StoryboardValidationTest(unittest.TestCase):
    def test_accepts_matching_indexed_project_visual_style(self) -> None:
        self.assertEqual(
            MODULE._validate_project_visual_style(
                {"category": "国风厚涂", "style": "国风厚涂"}, {"国风厚涂", "现代写实"}
            ),
            "国风厚涂",
        )

    def test_rejects_empty_mismatched_or_unindexed_project_visual_style(self) -> None:
        invalid_payloads = (
            {"category": "", "style": ""},
            {"category": "国风厚涂", "style": "现代真人电影质感"},
            {"category": "已删除风格", "style": "已删除风格"},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, "invalid_visual_style"):
                MODULE._validate_project_visual_style(payload, {"国风厚涂"})

    def test_documented_style_remains_selectable_without_optional_lora_weights(self) -> None:
        original_root = MODULE.LORA_ROOT
        with tempfile.TemporaryDirectory() as directory:
            MODULE.LORA_ROOT = Path(directory)
            documented = MODULE.LORA_ROOT / "国风浅涂"
            documented.mkdir(); (documented / "README.md").write_text("视觉规范", encoding="utf-8")
            (MODULE.LORA_ROOT / "空占位").mkdir()
            styles = MODULE._scan_lora_style_directories()
            self.assertEqual([(item["id"], item["model_count"]) for item in styles], [("国风浅涂", 0)])
        MODULE.LORA_ROOT = original_root

    def test_formats_structured_script_as_readable_paragraphs(self) -> None:
        content = MODULE._human_readable_script_content([{"画面":"门外","动作":"推门","台词":"回来。","旁、白":"夜深了。","情绪":"平静"}])
        self.assertEqual(content, "段落01\n画面：门外\n动作：推门\n台词：回来。\n旁白：夜深了。\n情绪：平静")

    def test_formats_pipe_script_as_one_category_per_line(self) -> None:
        content = MODULE._human_readable_script_content("段落01\n0-5秒｜画面：门外｜动作：推门｜台词/旁白：回来。｜情绪：平静")
        self.assertEqual(content, "段落01\n0-5秒\n画面：门外\n动作：推门\n台词/旁白：回来。\n情绪：平静")

    def test_accepts_complete_storyboard(self) -> None:
        self.assertEqual(len(MODULE._validate_storyboard(valid_shots(), 60, "")), 15)

    def test_rejects_fewer_than_fifteen_shots(self) -> None:
        with self.assertRaisesRegex(ValueError, "15-23"):
            MODULE._validate_storyboard(valid_shots(11, 60), 60, "")

    def test_rejects_short_total_duration(self) -> None:
        with self.assertRaisesRegex(ValueError, "总时长"):
            MODULE._validate_storyboard(valid_shots(15, 35), 60, "")

    def test_rejects_duplicate_visual_action(self) -> None:
        shots = valid_shots()
        shots[-1]["visual"] = shots[-2]["visual"]
        shots[-1]["action"] = shots[-2]["action"]
        with self.assertRaisesRegex(ValueError, "重复"):
            MODULE._validate_storyboard(shots, 60, "")

    def test_character_pose_templates_are_distinct_and_keep_full_body_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            templates = {}
            for pose in ("front_full", "side_90_full", "back_full"):
                target = Path(directory) / f"{pose}.ppm"
                MODULE._write_character_pose_template(target, pose, 200, 400)
                templates[pose] = target.read_bytes()
            self.assertNotEqual(templates["front_full"], templates["side_90_full"])
            self.assertNotEqual(templates["front_full"], templates["back_full"])
            self.assertNotEqual(templates["side_90_full"], templates["back_full"])
            self.assertTrue(all(len(content) > 200 * 400 * 3 for content in templates.values()))

    def test_workflow_next_steps_use_complete_episode_minimums(self) -> None:
        source = (MODULE_PATH.parents[1] / "frontend/App.vue").read_text(encoding="utf-8")
        for gate in (
            "outlineHasCompleteEpisode ? '生成剧本'",
            "scripts.length ? '生成分镜脚本'",
            "storyboardHasCompleteEpisode ? '生成图片'",
            "assetsReadyForShotImages ? '生成分镜画面'",
            "shotImagesReadyForVideo ? '生成分镜视频'",
            "hasMergeableEpisode ? '生成成片'",
        ):
            self.assertIn(gate, source)
        self.assertIn('至少完成一集实际引用的全部人物、道具和场景资产', source)
        self.assertNotIn(":next-label=\"assetStatus === 'confirmed' ? '生成分镜画面'", source)
        action_bar = (MODULE_PATH.parents[1] / "frontend/components/business/WorkflowActionBar.vue").read_text(encoding="utf-8")
        self.assertIn('<button v-if="nextLabel" class="workflow-action-next"', action_bar)
        self.assertNotIn('v-if="!running && nextLabel"', action_bar)

    def test_asset_census_is_scoped_to_completed_episode_and_enforces_cast(self) -> None:
        source = (MODULE_PATH.parents[1] / "frontend/App.vue").read_text(encoding="utf-8")
        self.assertIn("target_episodes:targetEpisodes", source)
        self.assertIn("required_characters:requiredCharacters", source)
        self.assertIn("targetScripts.map", source)
        self.assertIn("targetShots.map", source)
        self.assertNotIn('outlineStatus.value !== "confirmed" || assetStatus.value === "generating"', source)
        backend = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("不得加入只在其他集出现的人物", backend)
        self.assertIn("树木、花草、山景属于场景环境", backend)
        self.assertIn("金光、光晕、符文光效属于特效", backend)
        self.assertIn("for name in required_characters", backend)
        self.assertIn('"error":"stale_asset_census"', backend)
        self.assertIn('return characterProfiles.value.length;', source)
        self.assertIn('return propProfiles.value.length;', source)
        self.assertIn('return sceneProfiles.value.length;', source)
        self.assertIn(':next-disabled="!scriptHasCompleteEpisode"', source)

    def test_all_asset_baselines_expose_the_accept_action(self) -> None:
        source = (MODULE_PATH.parents[1] / "frontend/App.vue").read_text(encoding="utf-8")
        component = (MODULE_PATH.parents[1] / "frontend/components/business/UnifiedAssetCard.vue").read_text(encoding="utf-8")
        self.assertIn("function canAcceptAssetBaseline", source)
        self.assertIn('(slide.key === baselineSlideKey(kind) && canAcceptAssetBaseline(item))', source)
        self.assertIn('slide.variant?.status === "waiting_confirmation"', source)
        self.assertIn(':show-accept="slide.showAccept"', component)
        self.assertIn('v-if="canAcceptBaseline" @click="$emit(\'confirmBaseline\')"', component)
        self.assertNotIn("group.kind === 'character' && slide.key.startsWith('baseline:')", source)

    def test_completed_angle_jobs_are_recovered_after_page_interruption(self) -> None:
        source = (MODULE_PATH.parents[1] / "frontend/App.vue").read_text(encoding="utf-8")
        self.assertIn("const variantJobName =", source)
        self.assertIn("variant.image_url = completed.data.image.url", source)
        self.assertIn('variant.status = "confirmed"', source)
        self.assertIn('variant.status = "pending"', source)
        self.assertIn("hasCompleteAssetVariants(group.kind, item)", source)

    def test_character_baseline_uses_left_45_full_body_without_retry_loop(self) -> None:
        backend = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("for validation_attempt in range(5)", backend)
        self.assertIn("strict left 45-degree full-body view", backend)
        self.assertIn("complete head, hands and shoes visible", backend)
        self.assertIn('_validate_character_variant(image.get("url", ""), image, "left_45_full")', backend)

    def test_regeneration_purges_scoped_media_jobs_and_frontend_state(self) -> None:
        backend = MODULE_PATH.read_text(encoding="utf-8")
        frontend = (MODULE_PATH.parents[1] / "frontend/App.vue").read_text(encoding="utf-8")
        service = (MODULE_PATH.parents[1] / "frontend/services/asset.service.ts").read_text(encoding="utf-8")
        spec = (MODULE_PATH.parents[1] / "templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md").read_text(encoding="utf-8")
        self.assertIn('if parsed.path == "/api/assets/purge-generated"', backend)
        self.assertIn("def _purge_generated_assets", backend)
        self.assertIn("target.unlink(missing_ok=True)", backend)
        self.assertIn('postJson<T>("/api/assets/purge-generated"', service)
        self.assertIn("await assetService.purgeGenerated({ project_id:project.id, asset_kind:kind, asset_name:item.name })", frontend)
        self.assertIn("重新生成强制版本规则", spec)


if __name__ == "__main__":
    unittest.main()
