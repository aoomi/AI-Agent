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


if __name__ == "__main__":unittest.main()
