from __future__ import annotations
import unittest
import threading
from ai_agent_adapters import ProviderService,ProviderServiceError
class ProviderServiceRuntimeContractTest(unittest.TestCase):
 def test_settings_require_standard_json(self):
  base=dict(provider_id="provider",display_name="Provider",kind="video",endpoint="https://example.com",secret_reference="env://KEY",capabilities=("video",))
  for settings in ({"value":float("nan")},{"value":object()}):
   with self.subTest(settings=settings),self.assertRaisesRegex(ProviderServiceError,"standard JSON"):ProviderService().register(**base,settings=settings)
 def test_registration_rejects_ambiguous_runtime_values(self):
  base=dict(provider_id="provider",display_name="Provider",kind="video",endpoint="https://example.com",secret_reference="env://KEY",capabilities=("video",))
  for changes in ({"provider_id":1},{"capabilities":"video"},{"capabilities":("video","video")},{"endpoint":"https://user:pass@example.com"},{"timeout_seconds":True},{"settings":[]}):
   with self.subTest(changes=changes),self.assertRaisesRegex(ProviderServiceError,"configuration is invalid"):ProviderService().register(**{**base,**changes})
 def test_provider_controls_reject_non_string_identity(self):
  service=ProviderService()
  for operation in (lambda:service.get(1),lambda:service.test_connection(1)):
   with self.subTest(operation=operation),self.assertRaisesRegex(ProviderServiceError,"id is required"):operation()
 def test_inflight_health_check_fences_replace_and_uninstall(self):
  entered=threading.Event();release=threading.Event()
  class Checker:
   def check(self,_provider):entered.set();release.wait(2);return 1,None
  service=ProviderService(Checker());base=dict(provider_id="provider",display_name="Provider",kind="video",endpoint="https://example.com",secret_reference="env://KEY",capabilities=("video",))
  service.register(**base);thread=threading.Thread(target=lambda:service.test_connection("provider"));thread.start();self.assertTrue(entered.wait(1))
  with self.assertRaisesRegex(ProviderServiceError,"in-flight"):service.register(**base,replace=True)
  with self.assertRaisesRegex(ProviderServiceError,"in-flight"):service.unregister("provider")
  release.set();thread.join();self.assertTrue(service.unregister("provider"))
 def test_health_checker_result_contract_is_enforced(self):
  base=dict(provider_id="provider",display_name="Provider",kind="video",endpoint="https://example.com",secret_reference="env://KEY",capabilities=("video",))
  for result in ([],(True,None),(1,1),(1,"")):
   class Checker:
    def check(self,_provider):return result
   service=ProviderService(Checker());service.register(**base)
   with self.subTest(result=result),self.assertRaisesRegex(ProviderServiceError,"health"):service.test_connection("provider")
if __name__=="__main__":unittest.main()
