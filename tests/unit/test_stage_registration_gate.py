import json
from pathlib import Path

from plugins.builtin.short_drama.workflows.production_ledger import CANONICAL_STAGES


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = json.loads(
    (ROOT / "plugins/builtin/short_drama/workflows/stage.registrations.json").read_text(encoding="utf-8")
)["stages"]


def test_every_canonical_stage_has_all_four_runtime_registrations():
    assert tuple(row["stage"] for row in REGISTRY) == CANONICAL_STAGES
    for row in REGISTRY:
        assert row["startup_recovery"]
        assert row["langgraph_stage"] == row["stage"]
        assert row["project_storage"]
        assert row["frontend_continue"]
    for key in ("langgraph_stage", "project_storage"):
        values = [row[key] for row in REGISTRY]
        assert len(values) == len(set(values))


def test_registration_table_is_consumed_by_recovery_projection_and_frontend():
    backend = (ROOT / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    frontend_flow = (ROOT / "plugins/builtin/short_drama/frontend/utils/production-flow.ts").read_text(encoding="utf-8")
    app = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    assert 'PROJECT_STAGE_STORAGE[current_stage]' in backend
    assert 'stage.registrations.json' in frontend_flow
    for row in REGISTRY:
        assert f'function {row["frontend_continue"]}' in app


def test_startup_recovery_map_covers_previously_missing_stages():
    storage = {row["stage"]:row["project_storage"] for row in REGISTRY}
    assert storage["requirements"] == "requirements"
    assert storage["audio"] == "audio"
    assert storage["subtitle"] == "subtitle"
