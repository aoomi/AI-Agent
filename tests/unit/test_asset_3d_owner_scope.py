from pathlib import Path


def test_asset_3d_status_requires_owner_scope() -> None:
    root = Path(__file__).resolve().parents[2]
    backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    status = backend[backend.index('if parsed.path == "/api/assets/3d/status":'):backend.index('if parsed.path == "/api/projects":')]
    service = (root / "plugins/builtin/short_drama/frontend/services/asset.service.ts").read_text(encoding="utf-8")

    assert 'if not all(identity.values())' in status
    assert 'not _job_matches_scope(job, identity)' in status
    assert 'status3D<T>(jobId:string, identity:' in service
    assert 'new URLSearchParams({ job_id:jobId, ...identity })' in service
