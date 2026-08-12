"""Append-only provider usage and artifact audit ledger."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any,Mapping
from uuid import uuid4

class ProviderAuditError(ValueError):pass
@dataclass(frozen=True,slots=True)
class ProviderAuditRecord:
    audit_id:str;tenant_id:str;user_id:str;project_id:str;provider_id:str;capability:str;request_hash:str;input_tokens:int;output_tokens:int;duration_ms:int;cost_microunits:int;artifact_ids:tuple[str,...];artifact_checksums:tuple[str,...];status:str;error_code:str|None;created_at:str
class ProviderAuditLedger:
    def __init__(self):self._records:list[ProviderAuditRecord]=[]
    def record(self,*,tenant_id:str,user_id:str,project_id:str,provider_id:str,capability:str,request:Mapping[str,Any],input_tokens:int,output_tokens:int,duration_ms:int,cost_microunits:int,artifact_ids:tuple[str,...]=(),artifact_checksums:tuple[str,...]=(),status:str="completed",error_code:str|None=None)->ProviderAuditRecord:
        if not all(str(value).strip() for value in (tenant_id,user_id,project_id)):raise ProviderAuditError("audit owner scope is required")
        if status not in {"completed","failed","cancelled"}:raise ProviderAuditError("audit status is invalid")
        if any(value<0 for value in (input_tokens,output_tokens,duration_ms,cost_microunits)):raise ProviderAuditError("audit metrics cannot be negative")
        forbidden={"api_key","secret","token","password","credential"}
        if any(any(word in key.lower() for word in forbidden) for key in request):raise ProviderAuditError("audit request contains secret fields")
        digest=sha256(json.dumps(dict(request),sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
        record=ProviderAuditRecord(f"audit-{uuid4().hex}",tenant_id,user_id,project_id,provider_id,capability,digest,input_tokens,output_tokens,duration_ms,cost_microunits,artifact_ids,artifact_checksums,status,error_code,datetime.now(timezone.utc).isoformat());self._records.append(record);return record
    def list(self,tenant_id:str,user_id:str,project_id:str)->tuple[ProviderAuditRecord,...]:return tuple(r for r in self._records if r.tenant_id==tenant_id and r.user_id==user_id and r.project_id==project_id)
