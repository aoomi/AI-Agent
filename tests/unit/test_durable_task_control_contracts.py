from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from ai_agent_queue import DurableTaskRepository
class DurableTaskControlContractTest(unittest.TestCase):
 def test_controls_reject_ambiguous_runtime_inputs(self):
  with tempfile.TemporaryDirectory() as directory:
   repository=DurableTaskRepository(Path(directory)/"tasks.db")
   for operation in (lambda:repository.upsert_many("task",[],enqueue_projection=False),lambda:repository.upsert_many("task",{},enqueue_projection=1),lambda:repository.acknowledge_projections(("job",)),lambda:repository.acknowledge_projections([("job",True)]),lambda:repository.requeue_projection(" "),lambda:repository.get(" ",tenant_id="t",user_id="u",project_id="p"),lambda:repository.list(nonterminal_only=1)):
    with self.subTest(operation=operation),self.assertRaises(ValueError):operation()
   with self.assertRaises(ValueError):
    with repository.projection_lock("scope",ttl=True):pass
if __name__=="__main__":unittest.main()
