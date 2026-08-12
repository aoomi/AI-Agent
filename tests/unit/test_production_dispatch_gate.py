import importlib.util
from pathlib import Path
import tempfile

import pytest

from ai_agent_core import WorkerRegistry, WorkerSnapshot


ROOT = Path(__file__).resolve().parents[2]
BACKEND = (ROOT / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")


def test_production_gate_runs_before_remote_dispatch():
    handler = BACKEND[BACKEND.index("def do_POST"):BACKEND.index("if parsed.path in {\"/api/outline/plan\"")]
    gate = handler.index("_begin_production_request(body, production_stage)")
    dispatch = handler.index("_forward_production_request(parsed.path, body, dispatched)")
    assert gate < dispatch
    assert handler.count("_begin_production_request(body, production_stage)") == 1


def test_dispatched_header_requires_internal_token_or_exact_reservation():
    helper = BACKEND[BACKEND.index("def _authenticated_dispatched_request"):BACKEND.index("def _local_api")]
    assert 'get_header("X-Production-Internal")' in helper
    assert 'get_header("X-Production-Reservation")' in helper
    assert "worker_id != WORKER_ID" in helper
    assert "WORKER_REGISTRY.reservation_snapshot()" in helper
    assert 'raise PermissionError("production dispatch reservation is missing or expired")' in helper


def test_run_stage_internal_calls_use_process_private_dispatch_proof():
    local_api = BACKEND[BACKEND.index("def _local_api"):BACKEND.index("def _local_get")]
    assert '"X-Production-Internal":INTERNAL_DISPATCH_TOKEN' in local_api
    assert '"error":"invalid_production_dispatch"' in BACKEND


def test_dispatch_proof_rejects_forgery_and_accepts_exact_reservation():
    spec = importlib.util.spec_from_file_location("dispatch_proof_contract", ROOT / "plugins/builtin/short_drama/backend/compat_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._authenticated_dispatched_request("/api/videos/merge", {}, {}) is False
    with pytest.raises(PermissionError, match="invalid production dispatch proof"):
        module._authenticated_dispatched_request("/api/videos/merge", {}, {"X-Production-Dispatched":"1"})
    assert module._authenticated_dispatched_request(
        "/api/videos/merge", {}, {"X-Production-Dispatched":"1", "X-Production-Internal":module.INTERNAL_DISPATCH_TOKEN},
    ) is True
    with tempfile.TemporaryDirectory() as temporary:
        registry = WorkerRegistry(Path(temporary) / "workers.sqlite")
        module.WORKER_REGISTRY = registry
        registry.heartbeat(WorkerSnapshot(module.WORKER_ID, module.WORKER_SCOPE, ("video",), 1, 0, 0, 100, __import__("time").time(), endpoint="http://127.0.0.1:1"))
        registry.reserve("request-1", "video", service_scope=module.WORKER_SCOPE, reservation_ttl=60)
        assert module._authenticated_dispatched_request("/api/videos/merge", {}, {
            "X-Production-Dispatched":"1", "X-Production-Reservation":"request-1", "X-Production-Worker":module.WORKER_ID,
        }) is True
        with pytest.raises(PermissionError, match="missing or expired"):
            module._authenticated_dispatched_request("/api/videos/merge", {}, {
                "X-Production-Dispatched":"1", "X-Production-Reservation":"other", "X-Production-Worker":module.WORKER_ID,
            })


def test_dispatch_proof_is_bound_to_request_owner_scope():
    spec = importlib.util.spec_from_file_location("dispatch_owner_contract", ROOT / "plugins/builtin/short_drama/backend/compat_server.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as temporary:
        registry = WorkerRegistry(Path(temporary) / "workers.sqlite"); module.WORKER_REGISTRY = registry
        registry.heartbeat(WorkerSnapshot(module.WORKER_ID, module.WORKER_SCOPE, ("video",), 1, 0, 0, 100, __import__("time").time()))
        owner = {"tenant_id":"tenant", "user_id":"user", "project_id":"project"}
        registry.reserve("request-owner", "video", service_scope=module.WORKER_SCOPE, owner_scope="tenant\x1fuser\x1fproject", reservation_ttl=60)
        headers = {"X-Production-Dispatched":"1", "X-Production-Reservation":"request-owner", "X-Production-Worker":module.WORKER_ID}
        assert module._authenticated_dispatched_request("/api/videos/merge", owner, headers) is True
        with pytest.raises(PermissionError, match="missing or expired"):
            module._authenticated_dispatched_request("/api/videos/merge", {**owner, "user_id":"other"}, headers)
