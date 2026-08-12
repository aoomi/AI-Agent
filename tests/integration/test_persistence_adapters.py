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
 def test_empty_persistence_owner_scopes_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);state=SQLiteStateStore(root/"state.db");objects=LocalObjectStore(root/"objects");queue=SQLiteDurableQueue(root/"queue.db")
   with self.assertRaises(PersistenceError):state.put("","n","k",{})
   with self.assertRaises(PersistenceError):objects.put("","key",b"x")
   with self.assertRaises(PersistenceError):queue.enqueue("",{})
 def test_queue_rejects_sensitive_payloads(self):
  with tempfile.TemporaryDirectory() as d:
   queue=SQLiteDurableQueue(Path(d)/"queue.db")
   for payload in ({"access_token":"plaintext"},{"headers":{"Authorization":"Bearer plaintext"}},{"profiles":[{"client_secret":"plaintext"}]}):
    with self.subTest(payload=payload),self.assertRaisesRegex(PersistenceError,"sensitive fields"):queue.enqueue("t",payload)
 def test_state_rejects_sensitive_values(self):
  with tempfile.TemporaryDirectory() as d:
   state=SQLiteStateStore(Path(d)/"state.db")
   for value in ({"access_token":"plaintext"},{"headers":{"Authorization":"Bearer plaintext"}},{"profiles":[{"client_secret":"plaintext"}]}):
    with self.subTest(value=value),self.assertRaisesRegex(PersistenceError,"sensitive fields"):state.put("t","n","k",value)
 def test_persistence_rejects_non_json_and_non_binary_runtime_values(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);state=SQLiteStateStore(root/"state.db");queue=SQLiteDurableQueue(root/"queue.db");objects=LocalObjectStore(root/"objects")
   for operation in (lambda:state.put("t","n","k",{"value":float("nan")}),lambda:queue.enqueue("t",{"value":object()}),lambda:objects.put("t","key","text")):
    with self.subTest(operation=operation),self.assertRaises(PersistenceError):operation()
if __name__=="__main__":unittest.main()
