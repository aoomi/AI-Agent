from pathlib import Path


def test_agent_status_exports_persisted_heartbeat_without_faking_now() -> None:
    source = Path("plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    executor = source[source.index("def _execute_agent_job"):source.index("def _start_agent_job")]
    route = source[source.index('if parsed.path == "/api/assistant/agents/status":'):source.index('if parsed.path == "/api/assets/3d/status":')]
    assert 'while not heartbeat_stop.wait(5)' in executor
    assert 'current["heartbeat_at"] = datetime.now(UTC).isoformat()' in executor
    assert 'heartbeat_stop.set(); heartbeat_thread.join(timeout=1)' in executor
    assert 'payload["heartbeat_at"] = datetime.now(UTC).isoformat()' not in route
