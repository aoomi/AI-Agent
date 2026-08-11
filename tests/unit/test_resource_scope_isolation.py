from pathlib import Path


def test_resource_routes_require_full_owner_scope_and_scoped_media():
    source = Path("plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    get_block = source[source.index('if parsed.path == "/api/resources":'):source.index('if parsed.path == "/api/production/scopes":')]
    assert 'if not tenant_id or not user_id or scope not in' in get_block
    assert 'str(item.get("tenant_id") or "") == tenant_id' in get_block
    assert 'str(item.get("user_id") or "") == user_id' in get_block
    assert 'str(item.get("scope") or "") == scope' in get_block
    assert '"url":f"/api/resources/media?id={item.get(\'id\')}"' in get_block
    media = source[source.index('if parsed.path == "/api/resources/media":'):source.index('if parsed.path == "/api/production/scopes":')]
    assert 'if not resource_id or not tenant_id or not user_id or scope not in' in media
    assert 'str(item.get("id") or "") == resource_id' in media
    assert 'str(item.get("scope") or "") == scope' in media
    assert 'project_id and str(item.get("project_id") or "") == project_id' in media
    assert 'target.parent != resources_root' in media


def test_resource_create_and_delete_are_owner_scoped():
    source = Path("plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    post = source[source.index('if parsed.path == "/api/resources":', source.index("def do_POST")):]
    assert 'if not project_id or not self._project(project_id, tenant_id, user_id)' in post
    assert '"url": f"/api/resources/media?id={resource_id}"' in post
    delete = post[post.index('if parsed.path == "/api/resources/delete":'):]
    assert 'if not resource_id or not tenant_id or not user_id:' in delete
    assert 'item.get("tenant_id") == tenant_id and item.get("user_id") == user_id' in delete


def test_legacy_generic_media_route_rejects_resource_storage():
    source = Path("plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    media = source[source.index("    def _media(self, parsed)"):source.index("    def _json", source.index("    def _media(self, parsed)"))]
    assert 'Path(subfolder).parts[:1] == ("resources",)' in media
