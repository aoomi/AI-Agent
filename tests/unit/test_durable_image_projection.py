import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"


def load_backend(name: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DurableImageProjectionTests(unittest.TestCase):
    def test_image_endpoint_stage_resource_and_projection_contracts_agree(self):
        module = load_backend("compat_image_contract_test")
        for endpoint in (
            "/api/characters/generate",
            "/api/shots/generate",
            "/api/shots/repair",
            "/api/assistant/images/generate",
        ):
            self.assertEqual(module.PRODUCTION_ENDPOINT_STAGES[endpoint], "image")
            self.assertEqual(module.PRODUCTION_ENDPOINT_RESOURCES[endpoint], "image")
            projection = module._durable_task_projection("image", {
                "tenant_id":"tenant", "user_id":"user", "project_id":"project",
                "endpoint":endpoint, "status":"generating",
            })
            self.assertEqual(projection, (("tenant", "user", "project", "image"), "running"))

        self.assertEqual(module.PRODUCTION_ENDPOINT_STAGES["/api/assets/3d/generate"], "assets")
        self.assertEqual(module.PRODUCTION_ENDPOINT_RESOURCES["/api/assets/3d/generate"], "3d")
        projection = module._durable_task_projection("image", {
            "tenant_id":"tenant", "user_id":"user", "project_id":"project",
            "endpoint":"/api/assets/3d/generate", "workflow":"asset_3d", "status":"generating",
        })
        self.assertEqual(projection, (("tenant", "user", "project", "assets"), "running"))

    def test_character_generation_reports_only_image_for_all_terminal_transitions(self):
        module = load_backend("compat_character_projection_test")
        with TemporaryDirectory() as temporary:
            module.OUTPUT_ROOT = Path(temporary)
            cache = module.OUTPUT_ROOT / "narrative-cache"
            cache.mkdir(parents=True)
            module.IMAGE_JOBS_FILE = cache / "image-jobs.json"
            module.TASK_REPOSITORIES = {}
            module.SERVICE_SHUTTING_DOWN.clear()
            reports = []

            class Brain:
                def report(self, identity, stage, lifecycle, **evidence):
                    reports.append((dict(identity), stage, lifecycle, dict(evidence)))

            module.PRODUCTION_ORCHESTRATOR = Brain()
            for index, status in enumerate(("generating", "completed", "failed"), start=1):
                module._save_image_jobs({"jobs": {"character-job": {
                    "job_id":"character-job", "tenant_id":"tenant", "user_id":"user", "project_id":"project",
                    "endpoint":"/api/characters/generate", "asset_kind":"character", "status":status,
                    "error":"render failed" if status == "failed" else "", "updated_at":f"2026-08-11T00:00:0{index}Z",
                }}})

            self.assertEqual([item[1] for item in reports], ["image", "image", "image"])
            self.assertEqual([item[2] for item in reports], ["running", "pending_confirmation", "failed"])
            self.assertNotIn("assets", [item[1] for item in reports])

    def test_character_scene_and_prop_share_image_without_asset_3d_collision(self):
        module = load_backend("compat_asset_kind_projection_test")
        base = {
            "tenant_id":"tenant", "user_id":"user", "project_id":"project",
            "endpoint":"/api/characters/generate", "status":"queued",
        }
        for kind in ("character", "scene", "prop"):
            projection = module._durable_task_projection("image", {**base, "asset_kind":kind})
            self.assertEqual(projection[0][-1], "image")
        projection = module._durable_task_projection("image", {
            **base, "endpoint":"/api/assets/3d/generate", "workflow":"asset_3d", "asset_kind":"scene",
        })
        self.assertEqual(projection[0][-1], "assets")


if __name__ == "__main__":
    unittest.main()
