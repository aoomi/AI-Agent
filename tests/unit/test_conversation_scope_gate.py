from pathlib import Path


def test_conversation_routes_require_project_session_owner_scope() -> None:
    source = Path("plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    helper = source[source.index("def _valid_conversation_context"):source.index("def _conversation_messages")]
    routes = source[source.index('if parsed.path == "/api/assistant/history":'):source.index('if parsed.path == "/api/outline/plan":')]
    assert '("tenant_id", "user_id", "current_project", "session_id")' in helper
    assert routes.count('if not _valid_conversation_context(body.get("context"))') == 4
    assert routes.count('"error":"invalid_conversation_scope"') == 4
