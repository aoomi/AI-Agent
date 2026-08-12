from pathlib import Path
import importlib.util

import pytest


def _backend():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "compat_dispatch_json_contract_test",
        root / "plugins/builtin/short_drama/backend/compat_server.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._heartbeat_local_worker = lambda: None
    return module


@pytest.mark.parametrize("invalid", [float("nan"), object()])
def test_dispatch_rejects_non_standard_json_before_worker_reservation(invalid):
    module = _backend()

    class Registry:
        def __init__(self):
            self.calls = 0

        def reserve(self, *_args, **_kwargs):
            self.calls += 1
            raise AssertionError("invalid request must not reserve a worker")

    registry = Registry()
    module.WORKER_REGISTRY = registry

    with pytest.raises(ValueError, match="standard JSON"):
        module._forward_production_request(
            "/api/outline/plan",
            {"tenant_id": "t", "user_id": "u", "project_id": "p", "value": invalid},
            False,
        )

    assert registry.calls == 0
