from pathlib import Path


def test_assistant_execution_entries_require_conversation_scope() -> None:
    source = Path("plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    assistant = source[source.index('if parsed.path == "/api/assistant":'):source.index('if parsed.path == "/api/assistant/agents/start":')]
    route = source[source.index('if parsed.path == "/api/assistant/route":'):source.index('if parsed.path == "/api/assistant/history":')]
    assert assistant.count('if not _valid_conversation_context') == 2
    assert '"error":"invalid_agent_job_scope"' in assistant
    assert 'if not _valid_conversation_context' in route
    assert route.index('if not _valid_conversation_context') < route.index('_route_system_agent')
