from __future__ import annotations

import unittest
from pathlib import Path

from ai_agent_core import AgentCollaborationService, AgentConfigurationStore, AgentScheduler, AgentContextStore
from ai_agent_discovery import AgentRegistry, SkillRegistry
from ai_agent_llm_gateway import ModelDefinition, ModelRegistry


class SequencedInspector:
    def __init__(self): self.calls=0
    def inspect(self, handoff):
        self.calls+=1
        if self.calls==1:return {"read_only":True,"verdict":"changes_required","issues":[{"issue_id":"i-1","code":"FAIL","title":"失败","description":"整改","severity":"high","evidence_ids":[]}],"evidence":[]}
        return {"read_only":True,"verdict":"passed","issues":[],"evidence":[]}


class AgentCollaborationIntegrationTest(unittest.TestCase):
    def test_remediation_returns_to_mainline_and_reinspection_passes(self):
        root=Path(__file__).resolve().parents[2]; skills={s.skill_id:s for s in SkillRegistry(root/"plugins/builtin").scan()}; registry=AgentRegistry()
        developer,_=registry.register(skills["system_main_developer"]); inspector,_=registry.register(skills["system_inspector"])
        models=ModelRegistry();models.register(ModelDefinition.create(model_id="model",provider_id="provider",display_name="Model",capabilities={"chat","reasoning","tool_calling","structured_output"},context_window=32000))
        configs=AgentConfigurationStore(models)
        configs.create(agent=developer,skill=skills[developer.skill_id],model_id="model",updated_by_identity_id="owner")
        configs.create(agent=inspector,skill=skills[inspector.skill_id],model_id="model",updated_by_identity_id="owner")
        scheduler=AgentScheduler(registry,AgentContextStore()); service=AgentCollaborationService(configs,SequencedInspector(),scheduler)
        session=service.open_session(tenant_id="tenant",created_by_identity_id="owner",project_id="project",root_task_id="main",developer_agent_id=developer.agent_id,inspector_agent_id=inspector.agent_id,max_remediation_rounds=2)
        handoff=service.submit_for_inspection(session.session_id,task_id="main",context_reference="contexts/main.json")
        report=service.run_inspection(handoff.handoff_id); instruction=service.create_remediation(report.report_id)
        self.assertEqual(scheduler.remediation(instruction.instruction_id).root_task_id,"main")
        scheduler.complete_remediation(instruction.instruction_id)
        handoff=service.submit_for_inspection(session.session_id,task_id="main",context_reference="contexts/main-r1.json")
        self.assertEqual(service.run_inspection(handoff.handoff_id).verdict,"passed")
        self.assertEqual(service.get_session(session.session_id).status,"completed")


if __name__=="__main__":unittest.main()
