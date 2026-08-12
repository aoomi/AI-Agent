from pathlib import Path


def test_agent_job_status_requires_project_session_owner_scope() -> None:
    root = Path(__file__).resolve().parents[2]
    backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    route = backend[backend.index('if parsed.path == "/api/assistant/agents/status":'):backend.index('if parsed.path == "/api/assets/3d/status":')]
    service = (root / "plugins/builtin/short_drama/frontend/services/assistant.service.ts").read_text(encoding="utf-8")
    assert '("tenant_id", "user_id", "project_id", "session_id")' in route
    assert 'if not all(expected)' in route
    assert 'actual != expected' in route
    assert 'project_id:string; session_id:string' in service
