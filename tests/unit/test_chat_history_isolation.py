import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"


def _history_functions():
    tree = ast.parse(BACKEND.read_text(encoding="utf-8"))
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in {"_conversation_key", "_conversation_messages"}
    ]
    namespace = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(BACKEND), "exec"), namespace)
    return namespace["_conversation_messages"]


def test_history_never_falls_back_to_the_only_other_project_conversation():
    history = _history_functions()
    old = {"tenant_id":"t", "user_id":"u", "current_project":"old", "session_id":"chat"}
    new = {"tenant_id":"t", "user_id":"u", "current_project":"new", "session_id":"chat"}
    store = {"display_history": {"t:u:old:chat": [{"media":[{"url":"/old.png"}]}]}}
    assert history(store, old) == [{"media":[{"url":"/old.png"}]}]
    assert history(store, new) == []


def test_history_rejects_malformed_projection_instead_of_leaking_it():
    history = _history_functions()
    context = {"tenant_id":"t", "user_id":"u", "current_project":"p", "session_id":"chat"}
    assert history({"display_history": {"t:u:p:chat": {"media":"/wrong.png"}}}, context) == []
    assert history({"display_history": ["/old.png"]}, context) == []
