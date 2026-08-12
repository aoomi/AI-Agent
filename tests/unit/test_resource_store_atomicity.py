from pathlib import Path


def test_resource_routes_serialize_shared_json_access() -> None:
    source = Path("plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    get_routes = source[source.index('if parsed.path == "/api/resources":'):source.index('if parsed.path == "/api/production/scopes":')]
    post_routes = source[source.index('if parsed.path == "/api/resources":', source.index("def do_POST")):source.index('if parsed.path == "/api/projects/stage":', source.index('if parsed.path == "/api/resources":', source.index("def do_POST")))]
    assert 'RESOURCE_STORE_LOCK = threading.RLock()' in source
    assert get_routes.count('with RESOURCE_STORE_LOCK:') == 2
    assert post_routes.count('with RESOURCE_STORE_LOCK:') == 2
    assert post_routes.index('with RESOURCE_STORE_LOCK:') < post_routes.index('store = _load_resources()')
