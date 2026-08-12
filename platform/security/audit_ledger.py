"""Hash-chained mandatory behavior/export audit with enforced retention."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json
from threading import RLock
from typing import Any,Callable
from uuid import uuid4
class SecurityAuditError(ValueError):pass
@dataclass(frozen=True,slots=True)
class SecurityAuditEntry:
 entry_id:str;tenant_id:str;actor_id:str;action:str;resource_id:str;outcome:str;created_at:str;previous_hash:str;entry_hash:str
class SecurityAuditLedger:
 def __init__(self,retention_days:int=365):
  if isinstance(retention_days,bool) or not isinstance(retention_days,int) or retention_days<30:raise SecurityAuditError("audit retention must be an integer of at least 30 days")
  self.retention_days=retention_days;self._entries:list[SecurityAuditEntry]=[];self._lock=RLock()
 def append(self,*,tenant_id:str,actor_id:str,action:str,resource_id:str,outcome:str)->SecurityAuditEntry:
  if any(not isinstance(value,str) or not value.strip() for value in (tenant_id,actor_id,action,resource_id,outcome)):raise SecurityAuditError("audit fields are required")
  tenant_id,actor_id,action,resource_id,outcome=(value.strip() for value in (tenant_id,actor_id,action,resource_id,outcome))
  with self._lock:
   previous=self._entries[-1].entry_hash if self._entries else "0"*64;created=datetime.now(timezone.utc).isoformat();entry_id=f"security-audit-{uuid4().hex}";payload="|".join((entry_id,tenant_id,actor_id,action,resource_id,outcome,created,previous));digest=sha256(payload.encode()).hexdigest();entry=SecurityAuditEntry(entry_id,tenant_id,actor_id,action,resource_id,outcome,created,previous,digest);self._entries.append(entry);return entry
 def run(self,*,tenant_id:str,actor_id:str,action:str,resource_id:str,operation:Callable[[],Any])->Any:
  if not callable(operation):raise SecurityAuditError("audit operation must be callable")
  self.append(tenant_id=tenant_id,actor_id=actor_id,action=action,resource_id=resource_id,outcome="started")
  try:result=operation()
  except Exception:self.append(tenant_id=tenant_id,actor_id=actor_id,action=action,resource_id=resource_id,outcome="failed");raise
  self.append(tenant_id=tenant_id,actor_id=actor_id,action=action,resource_id=resource_id,outcome="completed");return result
 def export(self,*,tenant_id:str,actor_id:str)->bytes:
  if any(not isinstance(value,str) or not value.strip() for value in (tenant_id,actor_id)):raise SecurityAuditError("audit export identity is required")
  tenant_id,actor_id=tenant_id.strip(),actor_id.strip()
  with self._lock:data=json.dumps([asdict(e) for e in self._entries if e.tenant_id==tenant_id],sort_keys=True,separators=(",",":")).encode()
  self.append(tenant_id=tenant_id,actor_id=actor_id,action="audit.export",resource_id=tenant_id,outcome="completed");return data
 def verify(self)->bool:
  previous="0"*64
  with self._lock:entries=tuple(self._entries)
  for e in entries:
   payload="|".join((e.entry_id,e.tenant_id,e.actor_id,e.action,e.resource_id,e.outcome,e.created_at,previous))
   if e.previous_hash!=previous or sha256(payload.encode()).hexdigest()!=e.entry_hash:return False
   previous=e.entry_hash
  return True
 def entries(self)->tuple[SecurityAuditEntry,...]:
  with self._lock:return tuple(self._entries)
