import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest

from ai_agent_queue import TaskLeaseRepository
from plugins.builtin.short_drama.workflows.production_ledger import ProductionLedger


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"


def load_backend(name: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def authority(identity: dict, generation: int = 1) -> dict:
    return {
        **identity, "stage":"review_export", "scope_type":"episode", "scope_id":"upscale:1",
        "stage_substate":"upscale", "content_fingerprint":f"fingerprint-{generation}",
        "audit_batch_id":f"batch-{generation}", "generation":generation,
        "production_evidence":{"provider":"upscale"},
        "audit_evidence":{"final":{"status":"pass", "evidence":{"score":1}}},
        "progress":{"completed":1, "total":1},
    }


def claimed(module, identity: dict):
    context = module._claim_production_stage_request({**identity, "stage":"review_export"}, "review_export")
    event = context.__enter__()
    return context, event, int(event.lease_generation)


def test_cancel_first_publishes_neither_ledger_nor_graph() -> None:
    module = load_backend("upscale_atomic_cancel_first")
    identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
    with TemporaryDirectory() as temporary:
        module.TASK_LEASES = TaskLeaseRepository(Path(temporary) / "leases.sqlite")
        module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary) / "ledger.sqlite")
        record = authority(identity, module.PRODUCTION_LEDGER.reserve_upscale_generation(authority(identity)))
        reports = []
        module._production_orchestrator = lambda: SimpleNamespace(report=lambda *args, **kwargs: reports.append((args, kwargs)))
        context, event, generation = claimed(module, identity)
        event.set()
        with pytest.raises(RuntimeError, match="cancelled or lease lost"):
            module._commit_server_production_stage_result(
                identity, "review_export", {"operation":"upscale", "_authority_records":[record]}, event, generation,
            )
        with pytest.raises(RuntimeError, match="cancelled or lease lost"):
            context.__exit__(None, None, None)
        assert module.PRODUCTION_LEDGER.list(identity) == []
        assert reports == []


def test_commit_first_publishes_one_generation_and_consumes_lease() -> None:
    module = load_backend("upscale_atomic_commit_first")
    identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
    with TemporaryDirectory() as temporary:
        module.TASK_LEASES = TaskLeaseRepository(Path(temporary) / "leases.sqlite")
        module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary) / "ledger.sqlite")
        record = authority(identity, module.PRODUCTION_LEDGER.reserve_upscale_generation(authority(identity)))
        reports = []
        module._production_orchestrator = lambda: SimpleNamespace(report=lambda *args, **kwargs: reports.append((args, kwargs)) or {"status":"waiting_human"})
        context, event, generation = claimed(module, identity)
        workflow = module._commit_server_production_stage_result(
            identity, "review_export", {"operation":"upscale", "_authority_records":[record]}, event, generation,
        )
        context.__exit__(None, None, None)
        assert workflow["status"] == "waiting_human"
        assert len(module.PRODUCTION_LEDGER.list(identity)) == 1
        assert len(reports) == 1
        assert not module.TASK_LEASES.request_cancel(module._production_stage_lease_key(identity, "review_export"))


def test_graph_failure_rolls_back_entire_authority_batch() -> None:
    module = load_backend("upscale_atomic_graph_failure")
    identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
    with TemporaryDirectory() as temporary:
        module.TASK_LEASES = TaskLeaseRepository(Path(temporary) / "leases.sqlite")
        module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary) / "ledger.sqlite")
        record = authority(identity, module.PRODUCTION_LEDGER.reserve_upscale_generation(authority(identity)))
        module._production_orchestrator = lambda: SimpleNamespace(report=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("graph failed")))
        context, event, generation = claimed(module, identity)
        with pytest.raises(RuntimeError, match="graph failed"):
            module._commit_server_production_stage_result(
                identity, "review_export", {"operation":"upscale", "_authority_records":[record]}, event, generation,
            )
        context.__exit__(RuntimeError, RuntimeError("graph failed"), None)
        assert module.PRODUCTION_LEDGER.list(identity) == []


def test_lost_old_generation_cannot_publish_after_new_owner() -> None:
    module = load_backend("upscale_atomic_generation_fence")
    identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
    with TemporaryDirectory() as temporary:
        module.TASK_LEASES = TaskLeaseRepository(Path(temporary) / "leases.sqlite")
        module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary) / "ledger.sqlite")
        record = authority(identity, module.PRODUCTION_LEDGER.reserve_upscale_generation(authority(identity)))
        context, event, generation = claimed(module, identity)
        key = module._production_stage_lease_key(identity, "review_export")
        assert module.TASK_LEASES.release(key, event.lease_owner, generation)
        replacement = module.TASK_LEASES.acquire(key, "new-owner", ttl=45)
        assert replacement["generation"] > generation
        with pytest.raises(RuntimeError, match="cancelled or lease lost"):
            module._commit_server_production_stage_result(
                identity, "review_export", {"operation":"upscale", "_authority_records":[record]}, event, generation,
            )
        context.__exit__(RuntimeError, RuntimeError("lost"), None)
        assert module.PRODUCTION_LEDGER.list(identity) == []


def test_restart_recovery_fails_graph_commit_without_durable_authority() -> None:
    module = load_backend("upscale_atomic_restart_recovery")
    identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
    with TemporaryDirectory() as temporary:
        module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary) / "ledger.sqlite")
        module.PRODUCTION_ORCHESTRATOR = module.ProductionOrchestrator(Path(temporary) / "graph.sqlite")
        module._load_store = lambda: {"projects":[{"id":"p", "tenant_id":"t", "user_id":"u"}]}
        module.PRODUCTION_ORCHESTRATOR.report(
            identity, "review_export", "pending_confirmation", stage_generation=7,
            authority_commit={"kind":"upscale", "records":[{
                "scope_id":"upscale:1", "generation":3,
                "content_fingerprint":"missing", "audit_batch_id":"missing-batch",
            }]},
        )
        module._recover_production_workflows()
        state = module.PRODUCTION_ORCHESTRATOR.state(identity)
        assert state["stages"]["review_export"] == "failed"
        assert state["stage_generations"]["review_export"] == 7
        assert module.PRODUCTION_LEDGER.list(identity) == []
