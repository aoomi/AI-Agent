from pathlib import Path


def test_agent_job_start_idempotency_is_owner_scoped() -> None:
    source = Path("plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    route = source[source.index('if parsed.path == "/api/assistant/agents/start":'):source.index('if parsed.path == "/api/assistant/route":')]
    assert '("tenant_id", "user_id", "current_project", "session_id")' in route
    assert 'if not all(owner)' in route
    assert '== owner' in route
    assert route.index('if not all(owner)') < route.index('existing = next')
