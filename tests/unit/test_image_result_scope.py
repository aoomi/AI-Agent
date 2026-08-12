from pathlib import Path


def test_image_result_requires_owner_scope_before_recovery() -> None:
    root = Path(__file__).resolve().parents[2]
    backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    route = backend[backend.index('if parsed.path == "/api/characters/result":'):backend.index('if parsed.path == "/api/videos/result":')]
    service = (root / "plugins/builtin/short_drama/frontend/services/asset.service.ts").read_text(encoding="utf-8")
    assert 'if not all(identity.values())' in route
    assert '_job_matches_scope(item, identity)' in route
    assert route.index('_job_matches_scope(item, identity)') < route.index('job.get("status") == "generating"')
    assert 'characterResult<T>(name:string, identity:' in service
