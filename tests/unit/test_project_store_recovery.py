from __future__ import annotations

import importlib.util
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


MODULE_PATH = Path(__file__).parents[2] / "plugins/builtin/short_drama/backend/compat_server.py"


def load_backend():
    spec = importlib.util.spec_from_file_location("project_store_recovery_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def prepare(module, root: Path) -> None:
    module.OUTPUT_ROOT = root
    module.PROJECTS_FILE = root / "narrative-cache" / "projects.json"
    module.PROJECT_SNAPSHOTS_DIR = root / "narrative-cache" / "project-snapshots"
    module.PROJECT_VERSIONS_DIR = root / "narrative-cache" / "project-versions"
    module._save_store({"version":1, "projects":[{"id":"p1", "tenant_id":"t", "user_id":"u", "name":"demo", "stage_state":{}}]})
    # These tests exercise the atomic project-store/snapshot layer, not the
    # production-stage dependency graph. Keep orchestration gates out of this
    # unit boundary so arbitrary concurrent stage writes remain intentional.
    class StoreOnlyOrchestrator:
        @staticmethod
        def report(*_args, **_kwargs):
            return {"status":"store_only_test"}

    module._production_orchestrator = lambda: StoreOnlyOrchestrator()


def test_concurrent_stage_writes_preserve_every_stage() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        prepare(module, Path(temporary))
        stages = ("outline", "script", "storyboard", "assets", "shot_images", "video")
        with ThreadPoolExecutor(max_workers=len(stages)) as pool:
            list(pool.map(lambda stage: module._write_project_stage("p1", "t", "u", stage, {"value":stage, "census_version":2}), stages))
        project = module._load_store()["projects"][0]
        assert set(project["stage_state"]) == set(stages)
        assert all(project["stage_state"][stage]["data"]["value"] == stage for stage in stages)


def test_corrupt_store_recovers_latest_valid_snapshot() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        prepare(module, Path(temporary))
        module._write_project_stage("p1", "t", "u", "outline", {"value":"kept"})
        module.PROJECTS_FILE.write_text("{broken", encoding="utf-8")
        recovered = module._load_store()
        assert recovered["projects"][0]["id"] == "p1"


def test_project_version_contains_restorable_project() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        prepare(module, Path(temporary))
        project = module._load_store()["projects"][0]
        version = module._create_project_version(project, "manual", "test")
        record = module._read_project_version(version["version_id"])
        assert record and record["project"]["id"] == "p1"
        assert json.loads((module.PROJECT_VERSIONS_DIR / f'{version["version_id"]}.json').read_text())["reason"] == "test"


def test_late_public_projection_cannot_overwrite_fenced_terminal_stage() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        prepare(module, Path(temporary))
        store = module._load_store()
        store["projects"][0]["stage_state"]["assets"] = {
            "data":{"characters":[], "scenes":[{"name":"authoritative-scene"}], "props":[{"name":"authoritative-prop"}], "status":"waiting_confirmation", "error":"", "census_version":2},
            "updated_at":"2026-08-11T00:00:00+00:00", "revision":4, "authority_generation":7,
        }
        module._save_store(store)

        class FencedOrchestrator:
            reports = 0

            @classmethod
            def state(cls, _identity):
                return {
                    "status":"running",
                    "stage_events":{"assets":{"stage":"assets", "lifecycle":"pending_confirmation", "stage_generation":7}},
                }

            @classmethod
            def report(cls, *_args, **_kwargs):
                cls.reports += 1
                raise AssertionError("public projection must not report production authority")

        module._production_orchestrator = lambda: FencedOrchestrator()
        result = module._write_project_stage(
            "p1", "t", "u", "assets",
            {"characters":[{"name":"hero"}], "scenes":[], "props":[], "status":"generating", "error":"", "census_version":2},
            projection_only=True,
        )

        assert result["data"]["status"] == "waiting_confirmation"
        assert [item["name"] for item in result["data"]["characters"]] == ["hero"]
        assert [item["name"] for item in result["data"]["scenes"]] == ["authoritative-scene"]
        assert [item["name"] for item in result["data"]["props"]] == ["authoritative-prop"]
        assert result["authority_generation"] == 7
        assert FencedOrchestrator.reports == 0
