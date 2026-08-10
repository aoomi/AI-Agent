import unittest
from pathlib import Path
from ai_agent_core import AgentConfigurationStore
from ai_agent_discovery import AgentRegistry,IndustrySkillRegistry
from ai_agent_llm_gateway import ModelDefinition,ModelRegistry
class IndustryAgentConfigurationTest(unittest.TestCase):
 def test_each_process_robot_selects_and_versions_model_independently(self):
  skills=IndustrySkillRegistry(Path(__file__).resolve().parents[2]/"plugins").scan();registry=AgentRegistry();models=ModelRegistry()
  models.register(ModelDefinition.create(model_id="full",provider_id="p",display_name="Full",capabilities={"chat","reasoning","tool_calling","vision","structured_output"},context_window=32000));models.register(ModelDefinition.create(model_id="vision",provider_id="p",display_name="Vision",capabilities={"vision","structured_output"},context_window=32000));store=AgentConfigurationStore(models)
  outline=next(s for s in skills if s.process_id=="outline");review=next(s for s in skills if s.process_id=="review_export");a,_=registry.register_scoped(outline,"t","p");b,_=registry.register_scoped(review,"t","p");ca=store.create(agent=a,skill=outline,model_id="full",updated_by_identity_id="owner");cb=store.create(agent=b,skill=review,model_id="vision",updated_by_identity_id="owner");updated=store.update(a.agent_id,expected_version=1,updated_by_identity_id="owner",skill=outline,agent=a,settings={"temperature":0})
  self.assertEqual(updated.configuration_version,2);self.assertEqual(store.get(b.agent_id).configuration_version,1);self.assertNotEqual(ca.configuration_id,cb.configuration_id)
if __name__=="__main__":unittest.main()
