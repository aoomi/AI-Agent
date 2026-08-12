from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from plugins.builtin.short_drama.workflows.production_ledger import ProductionLedger, ProductionLedgerError


IDENTITY = {"tenant_id":"t", "user_id":"u", "project_id":"p"}


def authority(generation: int, fingerprint: str = "sha256-media") -> dict:
    return {**IDENTITY, "stage":"composition", "scope_type":"episode", "scope_id":"1",
            "stage_substate":"video_only", "content_fingerprint":fingerprint, "audit_batch_id":f"batch-{generation}",
            "generation":generation, "production_evidence":{"path":"master.mp4"},
            "audit_evidence":{"status":"not_applicable"}, "progress":{"completed":1, "total":1}}


def test_stage_authority_and_control_commit_share_one_transaction():
    with TemporaryDirectory() as temporary:
        ledger = ProductionLedger(Path(temporary) / "ledger.sqlite")
        with pytest.raises(RuntimeError, match="graph failed"):
            ledger.commit_stage_authorities([authority(1)], commit_callback=lambda: (_ for _ in ()).throw(RuntimeError("graph failed")))
        assert ledger.list(IDENTITY) == []
        committed = ledger.commit_stage_authorities([authority(1)], commit_callback=lambda: None)[0]
        assert committed["generation"] == 1
        assert committed["production_evidence"] == {"path":"master.mp4"}
        assert committed["audit_evidence"] == {"status":"not_applicable"}


def test_stage_authority_rejects_stale_and_same_generation_mutation():
    with TemporaryDirectory() as temporary:
        ledger = ProductionLedger(Path(temporary) / "ledger.sqlite")
        ledger.commit_stage_authorities([authority(2)])
        with pytest.raises(ProductionLedgerError, match="stale authoritative"):
            ledger.commit_stage_authorities([authority(1)])
        with pytest.raises(ProductionLedgerError, match="same-generation"):
            ledger.commit_stage_authorities([authority(2, "sha256-other")])


def test_projection_cannot_replace_server_stage_evidence():
    with TemporaryDirectory() as temporary:
        ledger = ProductionLedger(Path(temporary) / "ledger.sqlite")
        original = ledger.commit_stage_authorities([authority(1)])[0]
        projected = ledger.upsert_projection({**IDENTITY, "stage":"composition", "scope_type":"episode", "scope_id":"1",
            "lifecycle":"completed", "content_fingerprint":original["content_fingerprint"],
            "audit_batch_id":original["audit_batch_id"], "production_evidence":{"path":"forged.mp4"}})
        assert projected["production_evidence"] == {"path":"master.mp4"}


def test_server_stage_commit_wires_composition_audit_and_export_authorities():
    backend = (Path(__file__).resolve().parents[2] / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    block = backend[backend.index("def _commit_server_production_stage_result"):backend.index("def _cancel_production_stage")]
    assert 'stage == "composition"' in block
    assert 'result.get("operation") in {"audit", "export"}' in block
    assert "PRODUCTION_LEDGER.commit_stage_authorities(records, commit_callback=commit_graph_authority)" in block
    assert '"authority_batch_id":batch_id' in block
