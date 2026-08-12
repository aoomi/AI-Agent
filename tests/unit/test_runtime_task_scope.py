from pathlib import Path


def test_runtime_task_query_requires_complete_owner_scope() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    route = source[source.index('if parsed.path == "/api/tasks/runtime":'):source.index('if parsed.path == "/api/tasks/result":')]

    assert 'for key in ("tenant_id", "user_id", "project_id")' in route
    assert 'if not all(identity.values())' in route
    assert '"error":"invalid_task_scope"' in route
    assert 'tenant_id=identity["tenant_id"]' in route
    assert 'user_id=identity["user_id"]' in route
    assert 'project_id=identity["project_id"]' in route
