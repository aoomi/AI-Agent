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
 def test_corrupt_authority_and_outbox_payloads_fail_closed(self):
  with tempfile.TemporaryDirectory() as directory:
   repository=DurableTaskRepository(Path(directory)/"tasks.db")
   job={"tenant_id":"t","user_id":"u","project_id":"p","status":"queued"}
   repository.upsert_many("task",{"job":job},enqueue_projection=True)
   with repository._connection() as connection:
    connection.execute("UPDATE durable_tasks SET payload_json='NaN' WHERE job_id='job'")
    connection.execute("UPDATE task_projection_outbox SET payload_json='[]' WHERE job_id='job'")
   with self.assertRaisesRegex(ValueError,"payload is invalid"):repository.get("job",tenant_id="t",user_id="u",project_id="p")
   with self.assertRaisesRegex(ValueError,"payload is invalid"):repository.pending_projections(task_class="task")
 def test_list_uses_the_validated_normalized_scope(self):
  with tempfile.TemporaryDirectory() as directory:
   repository=DurableTaskRepository(Path(directory)/"tasks.db")
   repository.upsert("job","task",{"tenant_id":"t","user_id":"u","project_id":"p","status":"queued"})
   self.assertEqual([item["job_id"] for item in repository.list(tenant_id=" t ",user_id=" u ",project_id=" p ",task_class=" task ")],["job"])
 def test_batch_normalizes_identity_once_and_rejects_collisions(self):
  with tempfile.TemporaryDirectory() as directory:
   repository=DurableTaskRepository(Path(directory)/"tasks.db")
   job={"tenant_id":"t","user_id":"u","project_id":"p","status":"queued"}
   repository.upsert_many(" task ",{" job ":job})
   self.assertIsNotNone(repository.get("job",tenant_id="t",user_id="u",project_id="p"))
   with self.assertRaisesRegex(ValueError,"duplicate normalized"):
    repository.upsert_many("task",{"job":job," job ":job})
   self.assertEqual(len(repository.list()),1)
if __name__=="__main__":unittest.main()
