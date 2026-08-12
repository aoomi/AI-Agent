import unittest
from ai_agent_events import ProviderAuditError,ProviderAuditLedger
class ProviderAuditLedgerTest(unittest.TestCase):
    def test_records_usage_cost_duration_request_and_artifacts_in_scope(self):
        ledger=ProviderAuditLedger();record=ledger.record(tenant_id="t",user_id="u",project_id="p",provider_id="model",capability="chat",request={"model":"gpt"},input_tokens=10,output_tokens=4,duration_ms=80,cost_microunits=12,artifact_ids=("a",),artifact_checksums=("f"*64,))
        self.assertEqual(ledger.list("t","u","p"),(record,));self.assertEqual(ledger.list("t","other","p"),());self.assertEqual(len(record.request_hash),64)
    def test_secrets_and_negative_metrics_are_rejected(self):
        ledger=ProviderAuditLedger()
        with self.assertRaisesRegex(ProviderAuditError,"secret"):ledger.record(tenant_id="t",user_id="u",project_id="p",provider_id="x",capability="x",request={"api_key":"x"},input_tokens=0,output_tokens=0,duration_ms=0,cost_microunits=0)
        with self.assertRaisesRegex(ProviderAuditError,"negative"):ledger.record(tenant_id="t",user_id="u",project_id="p",provider_id="x",capability="x",request={},input_tokens=-1,output_tokens=0,duration_ms=0,cost_microunits=0)
if __name__=="__main__":unittest.main()
