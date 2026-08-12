from pathlib import Path


def test_project_version_reads_require_current_owner_scope() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    route = source[source.index('if parsed.path == "/api/projects/version":'):source.index('if parsed.path == "/api/tasks":')]

    owner_gate = 'self._project(project_id, query.get("tenant_id", [""])[0], query.get("user_id", [""])[0])'
    assert route.index(owner_gate) < route.index("if version_id:")
    assert 'if not project:' in route
    assert '"error":"project_not_found"' in route
