from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plugins.builtin.short_drama.workflows.production_ledger import ProductionLedger, ProductionLedgerError, canonical_stage


class ProductionLedgerRuntimeContractsTest(unittest.TestCase):
    def test_scope_identities_require_strings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger=ProductionLedger(Path(directory)/"ledger.sqlite")
            for payload in (
                {"tenant_id":1,"user_id":"u","project_id":"p"},
                {"tenant_id":"t","user_id":"u","project_id":"p","stage":1,"scope_type":"episode","scope_id":"1"},
                {"tenant_id":"t","user_id":"u","project_id":"p","stage":"video","scope_type":1,"scope_id":"1"},
            ):
                with self.subTest(payload=payload),self.assertRaises(ProductionLedgerError):ledger.list(payload) if "stage" not in payload else ledger.reserve_upscale_generation(payload)
        with self.assertRaises(ProductionLedgerError):canonical_stage(1)

    def test_upscale_cas_numbers_are_exact_integers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger=ProductionLedger(Path(directory)/"ledger.sqlite")
            base={"tenant_id":"t","user_id":"u","project_id":"p","stage":"review_export","scope_type":"episode","scope_id":"upscale:1"}
            generation=ledger.reserve_upscale_generation(base)
            for value in (True,1.5,"1"):
                payload={**base,"generation":value,"content_fingerprint":"f","audit_batch_id":"a","production_evidence":{"ok":True},"audit_evidence":{"ok":True}}
                with self.subTest(value=value),self.assertRaises(ProductionLedgerError):ledger.commit_upscale_authority(payload)
            payload={**base,"generation":generation,"content_fingerprint":"f","audit_batch_id":"a","production_evidence":{"ok":True},"audit_evidence":{"ok":True},"expected_revision":True}
            with self.assertRaisesRegex(ProductionLedgerError,"expected_revision"):ledger.commit_upscale_authority(payload)

    def test_generic_upserts_reject_pseudo_cas_and_lifecycle_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger=ProductionLedger(Path(directory)/"ledger.sqlite")
            base={"tenant_id":"t","user_id":"u","project_id":"p","stage":"video","scope_type":"shot","scope_id":"1"}
            for payload in ({**base,"generation":True},{**base,"expected_revision":True},{**base,"lifecycle":1}):
                with self.subTest(payload=payload),self.assertRaises(ProductionLedgerError):ledger.upsert(payload)
            for operation in (lambda:ledger.upsert_many([base],replace=1),lambda:ledger.upsert_many_projection([base],replace=1)):
                with self.subTest(operation=operation),self.assertRaisesRegex(ProductionLedgerError,"replace"):operation()

    def test_stage_authority_rejects_pseudo_generation_and_evidence_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger=ProductionLedger(Path(directory)/"ledger.sqlite")
            base={"tenant_id":"t","user_id":"u","project_id":"p","stage":"video","scope_type":"shot","scope_id":"1","production_evidence":{"ok":True},"audit_evidence":{"ok":True}}
            for changes in ({"generation":True,"content_fingerprint":"f","audit_batch_id":"a"},{"generation":1,"content_fingerprint":1,"audit_batch_id":"a"},{"generation":1,"content_fingerprint":"f","audit_batch_id":1}):
                with self.subTest(changes=changes),self.assertRaises(ProductionLedgerError):ledger.commit_stage_authorities([{**base,**changes}])

    def test_bulk_replace_validates_every_key_before_deleting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger=ProductionLedger(Path(directory)/"ledger.sqlite")
            base={"tenant_id":"t","user_id":"u","project_id":"p","stage":"video","scope_type":"shot","scope_id":"1"}
            ledger.upsert(base)
            for operation in (
                lambda:ledger.upsert_many([{**base,"scope_id":1}],replace=True),
                lambda:ledger.upsert_many_projection([object()],replace=True),
                lambda:ledger.upsert_many(None,replace=True),
            ):
                with self.subTest(operation=operation),self.assertRaises(ProductionLedgerError):operation()
                self.assertEqual(len(ledger.list(base)),1)


if __name__ == "__main__":unittest.main()
