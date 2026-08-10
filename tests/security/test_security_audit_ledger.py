import unittest
from ai_agent_security import SecurityAuditError,SecurityAuditLedger
class SecurityAuditLedgerTest(unittest.TestCase):
 def test_actions_and_exports_are_mandatorily_audited_and_chained(self):
  ledger=SecurityAuditLedger();self.assertEqual(ledger.run(tenant_id="t",actor_id="a",action="plugin.install",resource_id="p",operation=lambda:"ok"),"ok");data=ledger.export(tenant_id="t",actor_id="a");self.assertIn(b"plugin.install",data);self.assertEqual(ledger.entries()[-1].action,"audit.export");self.assertTrue(ledger.verify())
 def test_failures_are_audited_and_short_retention_rejected(self):
  with self.assertRaises(SecurityAuditError):SecurityAuditLedger(1)
  ledger=SecurityAuditLedger()
  with self.assertRaises(RuntimeError):ledger.run(tenant_id="t",actor_id="a",action="x",resource_id="r",operation=lambda:(_ for _ in ()).throw(RuntimeError()))
  self.assertEqual(ledger.entries()[-1].outcome,"failed")
if __name__=="__main__":unittest.main()
