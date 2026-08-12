from pathlib import Path


def test_assistant_read_modify_write_routes_share_one_lock() -> None:
    source = Path("plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    routes = source[source.index('if parsed.path == "/api/assistant/history":'):source.index('if parsed.path == "/api/outline/plan":')]
    assert 'ASSISTANT_STORE_LOCK = threading.RLock()' in source
    assert routes.count('with ASSISTANT_STORE_LOCK:') == 4
    for marker in ('display_history', 'store.setdefault("drafts"', 'store.setdefault("sessions"'):
        assert marker in routes
