from __future__ import annotations
import tempfile,unittest,math
from pathlib import Path
from ai_agent_queue import DurableTaskRepository
class DurableTaskControlContractTest(unittest.TestCase):
 def test_controls_reject_ambiguous_runtime_inputs(self):
  with self.assertRaises(ValueError):DurableTaskRepository("tasks.db")
  with tempfile.TemporaryDirectory() as directory:
   repository=DurableTaskRepository(Path(directory)/"tasks.db")
   for operation in (lambda:repository.upsert(1,"task",{}),lambda:repository.upsert("job",1,{}),lambda:repository.upsert("job","task",{"tenant_id":"t","user_id":"u","project_id":"p","stage":1}),lambda:repository.upsert("job","task",{"tenant_id":"t","user_id":"u","project_id":"p","pid":True}),lambda:repository.upsert("job","task",{"tenant_id":"t","user_id":"u","project_id":"p","value":object()}),lambda:repository.upsert_many("task",{1:{}},enqueue_projection=False),lambda:repository.upsert_many("task",[],enqueue_projection=False),lambda:repository.upsert_many("task",{},enqueue_projection=1),lambda:repository.pending_projections(task_class=1),lambda:repository.acknowledge_projections(("job",)),lambda:repository.acknowledge_projections([1]),lambda:repository.acknowledge_projections([("job",True)]),lambda:repository.requeue_projection(1),lambda:repository.requeue_projection(" "),lambda:repository.get(1,tenant_id="t",user_id="u",project_id="p"),lambda:repository.get("job",tenant_id=1,user_id="u",project_id="p"),lambda:repository.list(tenant_id=1),lambda:repository.list(nonterminal_only=1)):
    with self.subTest(operation=operation),self.assertRaises(ValueError):operation()
   with self.assertRaises(ValueError):
    with repository.projection_lock("scope",ttl=True):pass
   for value in (math.nan,math.inf):
    with self.assertRaises(ValueError):
     with repository.projection_lock("scope",ttl=value):pass
if __name__=="__main__":unittest.main()
