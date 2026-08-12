from __future__ import annotations
import unittest
from ai_agent_adapters import ProviderAdapterDefinition,ProviderAdapterRegistry,ProviderService
from ai_agent_circuit_breaker import ResilientProviderInvoker
from ai_agent_events import ProviderAuditLedger
from short_drama_workflows.provider_binding import ShortDramaProviderBindings
class Secrets:
    def resolve(self,r):return "resolved-secret"
class Executor:
    def execute(self,c,i,*,secret,timeout_seconds):
        if c.endswith(("outline","script","storyboard","asset_catalog")):return {"episodes":[1],"scenes":[1],"shots":[1],"characters":[],"props":[],"shot_prompts":[]}
        if c.endswith("composition"):return {"content":b"video","media_type":"video/mp4"}
        if c.endswith("review"):return {"approved":True,"issues":[]}
        return [{"content":b"real","media_type":"application/octet-stream","source_id":"source"}]
class Checker:
    def check(self,p):return 12,None
class ProviderProductionIntegrationTest(unittest.TestCase):
    def test_real_provider_binding_resilience_health_and_audit(self):
        registry=ProviderAdapterRegistry(Secrets());caps=frozenset(ShortDramaProviderBindings.REQUIRED);registry.register(ProviderAdapterDefinition("production","video",caps,"vault://production",30),Executor());routes={c:"production" for c in caps};binding=ShortDramaProviderBindings(registry,routes)
        resilient=ResilientProviderInvoker(lambda p,c,i:registry.invoke(p,c,i),sleeper=lambda _:None);result=resilient.call("production","short_drama.image",{})
        self.assertEqual(result.output[0]["source_id"],"source");self.assertEqual(binding.generate("short_drama.video",{})[0].content,b"real")
        service=ProviderService(Checker());service.register(provider_id="production",display_name="Production",kind="video",endpoint="https://provider.example/v1",secret_reference="vault://production",capabilities=tuple(caps));self.assertEqual(service.test_connection("production").status,"healthy")
        audit=ProviderAuditLedger();record=audit.record(tenant_id="tenant",user_id="user",project_id="project",provider_id="production",capability="short_drama.image",request={"prompt_hash":"abc"},input_tokens=0,output_tokens=0,duration_ms=12,cost_microunits=5,artifact_ids=("image-1",),artifact_checksums=("a"*64,));self.assertEqual(record.cost_microunits,5)
    def test_no_health_checker_never_reports_fake_success(self):
        service=ProviderService();service.register(provider_id="p",display_name="P",kind="image",endpoint="https://p.example",secret_reference="env://P_KEY",capabilities=("image",))
        with self.assertRaisesRegex(Exception,"real provider health checker"):service.test_connection("p")
    def test_local_model_endpoint_allows_loopback_http_only(self):
        service=ProviderService();item=service.register(provider_id="ollama",display_name="Ollama",kind="model",endpoint="http://127.0.0.1:11434/v1",secret_reference="env://LOCAL_MODEL_API_KEY",capabilities=("chat",));self.assertEqual(item.endpoint,"http://127.0.0.1:11434/v1")
        with self.assertRaisesRegex(Exception,"invalid"):service.register(provider_id="remote",display_name="Remote",kind="model",endpoint="http://example.com/v1",secret_reference="env://REMOTE_KEY",capabilities=("chat",))
    def test_nested_provider_settings_reject_credentials(self):
        service=ProviderService()
        with self.assertRaisesRegex(Exception,"secrets"):service.register(provider_id="p",display_name="P",kind="image",endpoint="https://p.example",secret_reference="env://P_KEY",capabilities=("image",),settings={"transport":{"headers":[{"authorization":"Bearer hidden"}]}})
    def test_provider_service_rejects_invalid_management_contracts(self):
        with self.assertRaisesRegex(Exception,"checker contract"):ProviderService(object())
        service=ProviderService()
        with self.assertRaisesRegex(Exception,"required"):service.get("")
        base=dict(provider_id="p",display_name="P",kind="image",endpoint="https://p.example",secret_reference="env://P_KEY",capabilities=("image",))
        for override in ({"provider_id":""},{"display_name":""},{"capabilities":("",)},{"timeout_seconds":0},{"enabled":1}):
            with self.subTest(override=override),self.assertRaisesRegex(Exception,"invalid"):service.register(**(base|override))
if __name__=="__main__":unittest.main()
