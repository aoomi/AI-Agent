import tempfile,unittest
from pathlib import Path
from ai_agent_adapters import LocalObjectStore,PersistenceError,SQLiteDurableQueue,SQLiteStateStore
class PersistenceAdaptersTest(unittest.TestCase):
 def test_state_objects_and_queue_survive_reopen(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);SQLiteStateStore(root/"state.db").put("t","n","k",{"v":1});self.assertEqual(SQLiteStateStore(root/"state.db").get("t","n","k"),{"v":1});LocalObjectStore(root/"objects").put("t","a/x",b"data");self.assertEqual(LocalObjectStore(root/"objects").get("t","a/x"),b"data");queue=SQLiteDurableQueue(root/"queue.db");item=queue.enqueue("t",{"x":1});self.assertEqual(SQLiteDurableQueue(root/"queue.db").claim("t").item_id,item.item_id)
 def test_object_traversal_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(PersistenceError):LocalObjectStore(Path(d)).put("t","../../x",b"x")
if __name__=="__main__":unittest.main()
