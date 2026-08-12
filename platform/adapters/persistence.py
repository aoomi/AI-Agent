"""Private-deployment database, object storage and durable queue adapters."""
from __future__ import annotations
from dataclasses import dataclass
import json,sqlite3
from threading import RLock
from pathlib import Path
from uuid import uuid4
class PersistenceError(ValueError):pass
class SQLiteStateStore:
 def __init__(self,path:Path):self.path=path;path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path,check_same_thread=False);self._lock=RLock();self.db.execute("CREATE TABLE IF NOT EXISTS state(tenant TEXT,namespace TEXT,key TEXT,value TEXT,PRIMARY KEY(tenant,namespace,key))");self.db.commit()
 def put(self,tenant,namespace,key,value):
  with self._lock:self.db.execute("INSERT OR REPLACE INTO state VALUES(?,?,?,?)",(tenant,namespace,key,json.dumps(value,sort_keys=True)));self.db.commit()
 def get(self,tenant,namespace,key):
  with self._lock:row=self.db.execute("SELECT value FROM state WHERE tenant=? AND namespace=? AND key=?",(tenant,namespace,key)).fetchone()
  if row is None:raise PersistenceError("state record not found")
  return json.loads(row[0])
class LocalObjectStore:
 def __init__(self,root:Path):self.root=root.resolve();self.root.mkdir(parents=True,exist_ok=True)
 def put(self,tenant,key,content):
  target=self._path(tenant,key);target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix(target.suffix+f".{uuid4().hex}.tmp");tmp.write_bytes(content);tmp.replace(target);return str(target.relative_to(self.root))
 def get(self,tenant,key):return self._path(tenant,key).read_bytes()
 def _path(self,tenant,key):
  target=(self.root/tenant/key).resolve()
  if not target.is_relative_to(self.root) or Path(key).is_absolute():raise PersistenceError("object key escapes tenant storage")
  return target
@dataclass(frozen=True,slots=True)
class DurableQueueItem:item_id:str;tenant_id:str;payload:dict;status:str
class SQLiteDurableQueue:
 def __init__(self,path:Path):path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path,check_same_thread=False);self._lock=RLock();self.db.execute("CREATE TABLE IF NOT EXISTS queue(id TEXT PRIMARY KEY,tenant TEXT,payload TEXT,status TEXT)");self.db.commit()
 def enqueue(self,tenant,payload):
  item=DurableQueueItem(f"queue-{uuid4().hex}",tenant,payload,"pending")
  with self._lock:self.db.execute("INSERT INTO queue VALUES(?,?,?,?)",(item.item_id,tenant,json.dumps(payload),item.status));self.db.commit()
  return item
 def claim(self,tenant):
  with self._lock:
   self.db.execute("BEGIN IMMEDIATE");row=self.db.execute("SELECT id,payload FROM queue WHERE tenant=? AND status='pending' ORDER BY rowid LIMIT 1",(tenant,)).fetchone()
   if row is None:self.db.commit();return None
   self.db.execute("UPDATE queue SET status='running' WHERE id=?",(row[0],));self.db.commit();return DurableQueueItem(row[0],tenant,json.loads(row[1]),"running")
