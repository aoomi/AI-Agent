import unittest
import threading
from ai_agent_security import SecurityAuditError,SecurityAuditLedger
class SecurityAuditLedgerTest(unittest.TestCase):
 def test_actions_and_exports_are_mandatorily_audited_and_chained(self):
  ledger=SecurityAuditLedger();self.assertEqual(ledger.run(tenant_id="t",actor_id="a",action="plugin.install",resource_id="p",operation=lambda:"ok"),"ok");data=ledger.export(tenant_id="t",actor_id="a");self.assertIn(b"plugin.install",data);self.assertEqual(ledger.entries()[-1].action,"audit.export");self.assertTrue(ledger.verify())
 def test_failures_are_audited_and_short_retention_rejected(self):
  with self.assertRaises(SecurityAuditError):SecurityAuditLedger(1)
  ledger=SecurityAuditLedger()

 def test_concurrent_appends_preserve_hash_chain(self):
  ledger=SecurityAuditLedger();barrier=threading.Barrier(9)
  def append(index):barrier.wait();ledger.append(tenant_id="t",actor_id="a",action="task.run",resource_id=str(index),outcome="completed")
  threads=[threading.Thread(target=append,args=(index,)) for index in range(8)]
  for thread in threads:thread.start()
  barrier.wait()
  for thread in threads:thread.join()
  self.assertEqual(len(ledger.entries()),8);self.assertTrue(ledger.verify())
  with self.assertRaises(RuntimeError):ledger.run(tenant_id="t",actor_id="a",action="x",resource_id="r",operation=lambda:(_ for _ in ()).throw(RuntimeError()))
  self.assertEqual(ledger.entries()[-1].outcome,"failed")
 def test_invalid_audit_operation_and_export_identity_are_rejected(self):
  ledger=SecurityAuditLedger()
  with self.assertRaisesRegex(SecurityAuditError,"callable"):ledger.run(tenant_id="t",actor_id="a",action="x",resource_id="r",operation=None)
  for scope in (("","a"),("t","")):
   with self.assertRaisesRegex(SecurityAuditError,"identity"):ledger.export(tenant_id=scope[0],actor_id=scope[1])
  self.assertEqual(ledger.entries(),())
if __name__=="__main__":unittest.main()
