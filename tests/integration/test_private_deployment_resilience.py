import tempfile,time,unittest
from pathlib import Path
from ai_agent_adapters import LocalObjectStore,SQLiteDurableQueue,SQLiteStateStore
class PrivateDeploymentResilienceTest(unittest.TestCase):
 def test_reopen_after_process_loss_preserves_database_queue_and_assets(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);state=SQLiteStateStore(root/"state.db");state.put("t","checkpoints","run",{"node":7});queue=SQLiteDurableQueue(root/"queue.db");queued=queue.enqueue("t",{"run":"run"});objects=LocalObjectStore(root/"objects");objects.put("t","assets/video.mp4",b"video")
   self.assertEqual(SQLiteStateStore(root/"state.db").get("t","checkpoints","run")["node"],7);self.assertEqual(SQLiteDurableQueue(root/"queue.db").claim("t").item_id,queued.item_id);self.assertEqual(LocalObjectStore(root/"objects").get("t","assets/video.mp4"),b"video")
 def test_capacity_baseline(self):
  with tempfile.TemporaryDirectory() as d:
   queue=SQLiteDurableQueue(Path(d)/"queue.db");start=time.monotonic()
   for index in range(2000):queue.enqueue("tenant",{"index":index})
   self.assertLess(time.monotonic()-start,10);self.assertIsNotNone(queue.claim("tenant"))
