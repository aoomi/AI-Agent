from __future__ import annotations

import unittest

from ai_agent_core import AgentCollaborationError,AgentCollaborationService


class _Configurations:
 def get(self,_):raise AssertionError("configuration lookup must not run")

class CollaborationRoundContractTest(unittest.TestCase):
 def test_open_rejects_pseudo_round_before_configuration_lookup(self):
  service=AgentCollaborationService(_Configurations(),None)
  for value in (True,1.5):
   with self.subTest(value=value),self.assertRaisesRegex(AgentCollaborationError,"between 1 and 100"):
    service.open_session(tenant_id="tenant",created_by_identity_id="owner",project_id="project",root_task_id="task",developer_agent_id="developer",inspector_agent_id="inspector",max_remediation_rounds=value)  # type: ignore[arg-type]

if __name__=="__main__":unittest.main()
