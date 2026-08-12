from __future__ import annotations
import unittest
import threading
from ai_agent_adapters import ProviderAdapterDefinition,ProviderAdapterError,ProviderAdapterRegistry

class Secrets:
    def resolve(self,reference):return {"vault://text":"real-secret"}.get(reference,"")
class Executor:
    def __init__(self):self.calls=[]
    def execute(self,capability,inputs,*,secret,timeout_seconds):self.calls.append((capability,dict(inputs),secret,timeout_seconds));return {"id":"real-output"}

class ProviderAdapterRegistryTest(unittest.TestCase):
    def test_definition_and_invoke_runtime_contracts_are_rejected(self):
        for kwargs in ({"capabilities":frozenset({" "})},{"capabilities":("generate.image",)},{"provider_id":1},{"timeout_seconds":True},{"enabled":1},{"settings":[]}):
            values=dict(provider_id="p",kind="image",capabilities=frozenset({"generate.image"}),secret_reference="vault://text",timeout_seconds=30);values.update(kwargs)
            with self.subTest(kwargs=kwargs),self.assertRaises(ProviderAdapterError):ProviderAdapterDefinition(**values)
        registry=ProviderAdapterRegistry(Secrets());registry.register(ProviderAdapterDefinition("p","image",frozenset({"generate.image"}),"vault://text",30),Executor())
        with self.assertRaisesRegex(ProviderAdapterError,"mapping inputs"):registry.invoke("p","generate.image",[])
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
    def test_registry_rejects_invalid_provider_control_contracts(self):
        with self.assertRaisesRegex(ProviderAdapterError,"resolver contract"):ProviderAdapterRegistry(object())
        registry=ProviderAdapterRegistry(Secrets());definition=ProviderAdapterDefinition("p","image",frozenset({"generate.image"}),"vault://text",30)
        with self.assertRaisesRegex(ProviderAdapterError,"definition contract"):registry.register(object(),Executor())
        with self.assertRaisesRegex(ProviderAdapterError,"executor contract"):registry.register(definition,object())
        with self.assertRaisesRegex(ProviderAdapterError,"replace control"):registry.register(definition,Executor(),replace=1)
        for operation in (lambda:registry.get(""),lambda:registry.get(1),lambda:registry.list(kind="unknown"),lambda:registry.invoke("","generate.image",{}),lambda:registry.invoke("p",1,{})):
            with self.assertRaises(ProviderAdapterError):operation()

    def test_inflight_provider_cannot_be_replaced_or_unregistered(self):
        entered=threading.Event();release=threading.Event()
        class SlowExecutor:
            def execute(self,*_args,**_kwargs):entered.set();release.wait(2);return {"ok":True}
        registry=ProviderAdapterRegistry(Secrets());definition=ProviderAdapterDefinition("p","image",frozenset({"generate.image"}),"vault://text",30)
        registry.register(definition,SlowExecutor());thread=threading.Thread(target=lambda:registry.invoke("p","generate.image",{}));thread.start();self.assertTrue(entered.wait(1))
        with self.assertRaisesRegex(ProviderAdapterError,"in-flight"):registry.unregister("p")
        with self.assertRaisesRegex(ProviderAdapterError,"in-flight"):registry.register(definition,Executor(),replace=True)
        release.set();thread.join();self.assertTrue(registry.unregister("p"))

if __name__=="__main__":unittest.main()
