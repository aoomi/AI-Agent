from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = (ROOT / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")


def test_video_result_job_id_cannot_bypass_owner_scope():
    route = BACKEND[BACKEND.index('if parsed.path == "/api/videos/result"'):BACKEND.index("def do_POST")]
    assert 'if not all(identity.values())' in route
    assert '_job_matches_scope(job, identity)' in route
    assert 'bool(requested_job_id and job_id == requested_job_id)' in route
