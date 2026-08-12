"""Append-only provider usage and artifact audit ledger."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
import json
from types import MappingProxyType
from threading import RLock
from typing import Any,Mapping
from uuid import uuid4

class ProviderAuditError(ValueError):pass
@dataclass(frozen=True,slots=True)
class ProviderAuditRecord:
    audit_id:str;tenant_id:str;user_id:str;project_id:str;provider_id:str;capability:str;request_hash:str;input_tokens:int;output_tokens:int;duration_ms:int;cost_microunits:int;artifact_ids:tuple[str,...];artifact_checksums:tuple[str,...];status:str;error_code:str|None;created_at:str
class ProviderAuditLedger:
    def __init__(self):self._records:list[ProviderAuditRecord]=[];self._lock=RLock()
    def record(self,*,tenant_id:str,user_id:str,project_id:str,provider_id:str,capability:str,request:Mapping[str,Any],input_tokens:int,output_tokens:int,duration_ms:int,cost_microunits:int,artifact_ids:tuple[str,...]=(),artifact_checksums:tuple[str,...]=(),status:str="completed",error_code:str|None=None)->ProviderAuditRecord:
        if any(not isinstance(value,str) or not value.strip() for value in (tenant_id,user_id,project_id)):raise ProviderAuditError("audit owner scope is required")
        if any(not isinstance(value,str) or not value.strip() for value in (provider_id,capability)):raise ProviderAuditError("audit provider and capability are required")
        if not isinstance(status,str) or status not in {"completed","failed","cancelled"}:raise ProviderAuditError("audit status is invalid")
        metrics=(input_tokens,output_tokens,duration_ms,cost_microunits)
        if any(isinstance(value,bool) or not isinstance(value,int) or value<0 for value in metrics):raise ProviderAuditError("audit metrics must be non-negative integers")
        if not isinstance(request,Mapping):raise ProviderAuditError("audit request must be a mapping")
        if not isinstance(artifact_ids,tuple) or not isinstance(artifact_checksums,tuple):raise ProviderAuditError("audit artifacts must be tuples")
        if len(artifact_ids)!=len(artifact_checksums):raise ProviderAuditError("audit artifact identifiers and checksums must align")
        if any(not isinstance(value,str) or not value.strip() for value in (*artifact_ids,*artifact_checksums)):raise ProviderAuditError("audit artifact identifiers and checksums are required")
        if error_code is not None and (not isinstance(error_code,str) or not error_code.strip()):raise ProviderAuditError("audit error_code is invalid")
        forbidden={"api_key","secret","token","password","credential","authorization"}
        def contains_secret(value:Any)->bool:
            if isinstance(value,Mapping):return any(any(word in str(key).lower() for word in forbidden) or contains_secret(item) for key,item in value.items())
            if isinstance(value,(list,tuple)):return any(contains_secret(item) for item in value)
            return False
        if contains_secret(request):raise ProviderAuditError("audit request contains secret fields")
        try:digest=sha256(json.dumps(dict(request),sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
        except (TypeError,ValueError) as error:raise ProviderAuditError("audit request must be standard JSON") from error
        record=ProviderAuditRecord(f"audit-{uuid4().hex}",tenant_id.strip(),user_id.strip(),project_id.strip(),provider_id.strip(),capability.strip(),digest,input_tokens,output_tokens,duration_ms,cost_microunits,tuple(value.strip() for value in artifact_ids),tuple(value.strip() for value in artifact_checksums),status,error_code.strip() if error_code else None,datetime.now(timezone.utc).isoformat())
        with self._lock:self._records.append(record)
        return record
    def list(self,tenant_id:str,user_id:str,project_id:str)->tuple[ProviderAuditRecord,...]:
        if any(not isinstance(value,str) or not value.strip() for value in (tenant_id,user_id,project_id)):raise ProviderAuditError("audit owner scope is required")
        tenant_id,user_id,project_id=(value.strip() for value in (tenant_id,user_id,project_id))
        with self._lock:return tuple(r for r in self._records if r.tenant_id==tenant_id and r.user_id==user_id and r.project_id==project_id)
