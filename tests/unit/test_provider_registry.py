from __future__ import annotations
import unittest
from ai_agent_adapters import ProviderAdapterDefinition,ProviderAdapterError,ProviderAdapterRegistry

class Secrets:
    def resolve(self,reference):return {"vault://text":"real-secret"}.get(reference,"")
class Executor:
    def __init__(self):self.calls=[]
    def execute(self,capability,inputs,*,secret,timeout_seconds):self.calls.append((capability,dict(inputs),secret,timeout_seconds));return {"id":"real-output"}

class ProviderAdapterRegistryTest(unittest.TestCase):
    def test_registers_and_invokes_each_real_provider_kind(self):
        registry=ProviderAdapterRegistry(Secrets())
        for kind in ("text","image","video","audio"):
            executor=Executor();definition=ProviderAdapterDefinition(f"{kind}-provider",kind,frozenset({f"generate.{kind}"}),"vault://text",30)
            registry.register(definition,executor);result=registry.invoke(definition.provider_id,f"generate.{kind}",{"prompt":"x"})
            self.assertEqual(result.kind,kind);self.assertEqual(executor.calls[0][2],"real-secret")
    def test_disabled_unauthorized_and_missing_secret_fail_explicitly(self):
        registry=ProviderAdapterRegistry(Secrets());executor=Executor()
        registry.register(ProviderAdapterDefinition("p","image",frozenset({"generate.image"}),"vault://text",30,False),executor)
        with self.assertRaisesRegex(ProviderAdapterError,"disabled"):registry.invoke("p","generate.image",{})
        registry.register(ProviderAdapterDefinition("p2","image",frozenset({"generate.image"}),"vault://missing",30),executor)
        with self.assertRaisesRegex(ProviderAdapterError,"authorized"):registry.invoke("p2","generate.video",{})
        with self.assertRaisesRegex(ProviderAdapterError,"resolved"):registry.invoke("p2","generate.image",{})
    def test_nested_adapter_settings_reject_credentials(self):
        with self.assertRaisesRegex(ProviderAdapterError,"secrets"):
            ProviderAdapterDefinition("p","image",frozenset({"generate.image"}),"vault://text",30,settings={"transport":{"headers":[{"authorization":"Bearer hidden"}]}})

if __name__=="__main__":unittest.main()
