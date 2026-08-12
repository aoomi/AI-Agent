"""Private-deployment database, object storage and durable queue adapters."""
from __future__ import annotations
from dataclasses import dataclass
import json,sqlite3
from threading import RLock
from pathlib import Path
from uuid import uuid4
class PersistenceError(ValueError):pass
class SQLiteStateStore:
 def __init__(self,path:Path):
  if not isinstance(path,Path):raise PersistenceError("state path must be a Path")
  self.path=path;path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path,check_same_thread=False);self._lock=RLock();self.db.execute("CREATE TABLE IF NOT EXISTS state(tenant TEXT,namespace TEXT,key TEXT,value TEXT,PRIMARY KEY(tenant,namespace,key))");self.db.commit()
 def put(self,tenant,namespace,key,value):
  if any(not isinstance(item,str) for item in (tenant,namespace,key)) or not all(item.strip() for item in (tenant,namespace,key)):raise PersistenceError("state owner and key are required")
  forbidden=("secret","token","password","api_key","authorization","credential")
  def contains_sensitive(item):
   if isinstance(item,dict):return any(any(word in str(field).lower() for word in forbidden) or contains_sensitive(child) for field,child in item.items())
   if isinstance(item,(list,tuple,set,frozenset)):return any(contains_sensitive(child) for child in item)
   return False
  if contains_sensitive(value):raise PersistenceError("state value contains sensitive fields")
  try:encoded=json.dumps(value,sort_keys=True,allow_nan=False)
  except (TypeError,ValueError) as error:raise PersistenceError("state value must be JSON serializable") from error
  with self._lock:self.db.execute("INSERT OR REPLACE INTO state VALUES(?,?,?,?)",(tenant,namespace,key,encoded));self.db.commit()
 def get(self,tenant,namespace,key):
  if any(not isinstance(item,str) for item in (tenant,namespace,key)) or not all(item.strip() for item in (tenant,namespace,key)):raise PersistenceError("state owner and key are required")
  with self._lock:row=self.db.execute("SELECT value FROM state WHERE tenant=? AND namespace=? AND key=?",(tenant,namespace,key)).fetchone()
  if row is None:raise PersistenceError("state record not found")
  try:return json.loads(row[0],parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))
  except (json.JSONDecodeError,ValueError,TypeError) as error:raise PersistenceError("state record is invalid") from error
class LocalObjectStore:
 def __init__(self,root:Path):
  if not isinstance(root,Path):raise PersistenceError("object root must be a Path")
  self.root=root.resolve();self.root.mkdir(parents=True,exist_ok=True)
 def put(self,tenant,key,content):
  if not isinstance(content,(bytes,bytearray,memoryview)):raise PersistenceError("object content must be bytes")
  target=self._path(tenant,key);target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix(target.suffix+f".{uuid4().hex}.tmp");tmp.write_bytes(content);tmp.replace(target);return str(target.relative_to(self.root))
 def get(self,tenant,key):return self._path(tenant,key).read_bytes()
 def _path(self,tenant,key):
  if not isinstance(tenant,str) or not isinstance(key,str):raise PersistenceError("object owner and key are required")
  tenant_path,key_path=Path(tenant.strip()),Path(key.strip())
  if (not tenant.strip() or not key.strip() or tenant_path.is_absolute() or key_path.is_absolute()
      or len(tenant_path.parts)!=1 or tenant_path.parts[0] in (".","..") or any(part in (".","..") for part in key_path.parts)):
   raise PersistenceError("object owner and key are required")
  tenant_root=(self.root/tenant_path).resolve();target=(tenant_root/key_path).resolve()
  if not target.is_relative_to(tenant_root):raise PersistenceError("object key escapes tenant storage")
  return target
@dataclass(frozen=True,slots=True)
class DurableQueueItem:item_id:str;tenant_id:str;payload:dict;status:str
class SQLiteDurableQueue:
 def __init__(self,path:Path):
  if not isinstance(path,Path):raise PersistenceError("queue path must be a Path")
  path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path,check_same_thread=False);self._lock=RLock();self.db.execute("CREATE TABLE IF NOT EXISTS queue(id TEXT PRIMARY KEY,tenant TEXT,payload TEXT,status TEXT)");self.db.commit()
 def enqueue(self,tenant,payload):
  if not isinstance(tenant,str) or not tenant.strip():raise PersistenceError("queue tenant is required")
  if not isinstance(payload,dict):raise PersistenceError("queue payload must be an object")
  forbidden=("secret","token","password","api_key","authorization","credential")
  def contains_sensitive(value):
   if isinstance(value,dict):return any(any(word in str(key).lower() for word in forbidden) or contains_sensitive(item) for key,item in value.items())
   if isinstance(value,(list,tuple,set,frozenset)):return any(contains_sensitive(item) for item in value)
   return False
  if contains_sensitive(payload):raise PersistenceError("queue payload contains sensitive fields")
  try:encoded=json.dumps(payload,allow_nan=False)
  except (TypeError,ValueError) as error:raise PersistenceError("queue payload must be JSON serializable") from error
  payload_snapshot=json.loads(encoded);item=DurableQueueItem(f"queue-{uuid4().hex}",tenant,payload_snapshot,"pending")
  with self._lock:self.db.execute("INSERT INTO queue VALUES(?,?,?,?)",(item.item_id,tenant,encoded,item.status));self.db.commit()
  return item
 def claim(self,tenant):
  if not isinstance(tenant,str) or not tenant.strip():raise PersistenceError("queue tenant is required")
  with self._lock:
   self.db.execute("BEGIN IMMEDIATE");row=self.db.execute("SELECT id,payload FROM queue WHERE tenant=? AND status='pending' ORDER BY rowid LIMIT 1",(tenant,)).fetchone()
   if row is None:self.db.commit();return None
   try:payload=json.loads(row[1],parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))
   except (json.JSONDecodeError,ValueError,TypeError) as error:self.db.rollback();raise PersistenceError("queue record is invalid") from error
   if not isinstance(payload,dict):self.db.rollback();raise PersistenceError("queue record is invalid")
   self.db.execute("UPDATE queue SET status='running' WHERE id=?",(row[0],));self.db.commit();return DurableQueueItem(row[0],tenant,payload,"running")
