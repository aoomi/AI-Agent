import unittest
from ai_agent_adapters import ProviderAdapterDefinition,ProviderAdapterRegistry
from short_drama_workflows.provider_binding import ShortDramaProviderBindingError,ShortDramaProviderBindings
class Secrets:
    def resolve(self,r):return "secret"
class Executor:
    def execute(self,c,i,*,secret,timeout_seconds):
        if c.endswith("outline"):return {"episodes":[1]}
        if c.endswith("composition"):return {"content":b"video","media_type":"video/mp4"}
        if c.endswith("review"):return {"approved":True,"issues":[]}
        return [{"content":b"x","media_type":"application/octet-stream","source_id":"1"}]
class ShortDramaProviderBindingsTest(unittest.TestCase):
    def setUp(self):
        self.registry=ProviderAdapterRegistry(Secrets());caps=frozenset(ShortDramaProviderBindings.REQUIRED);self.registry.register(ProviderAdapterDefinition("real","video",caps,"vault://real",30),Executor());self.routes={c:"real" for c in caps}
    def test_all_generation_classes_use_authorized_registry(self):
        binding=ShortDramaProviderBindings(self.registry,self.routes);self.assertEqual(binding.generate("short_drama.outline",{})["episodes"],[1]);self.assertEqual(binding.generate("short_drama.image",{})[0].content,b"x");self.assertEqual(binding.compose({"videos":[b"x"]}).media_type,"video/mp4");self.assertTrue(binding.review(b"x","video/mp4").approved)
    def test_missing_route_is_explicit(self):
        routes=dict(self.routes);routes.pop("short_drama.audio")
        with self.assertRaisesRegex(ShortDramaProviderBindingError,"missing provider routes"):ShortDramaProviderBindings(self.registry,routes)
if __name__=="__main__":unittest.main()
