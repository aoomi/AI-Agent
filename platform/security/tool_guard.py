"""Skill tool authorization, input sanitization and output redaction."""
from __future__ import annotations
import re
import math
from typing import Any,Mapping
class ToolGuardError(PermissionError):pass
class SkillToolGuard:
 SECRET_KEYS=frozenset({"api_key","secret","token","password","credential","authorization"});HIGH_RISK=frozenset({"workspace.write","process.execute","network.unrestricted","data.delete"})
 def authorize(self,*,role:str,tool:str,declared_permissions:frozenset[str],explicit_grants:frozenset[str]=frozenset())->None:
  if (not isinstance(role,str) or not isinstance(tool,str) or not isinstance(declared_permissions,frozenset) or not isinstance(explicit_grants,frozenset)
      or not role.strip() or not tool.strip() or any(not isinstance(value,str) or not value.strip() for value in (*declared_permissions,*explicit_grants))):raise ToolGuardError("tool authorization contract is invalid")
  role,tool=role.strip(),tool.strip()
  if tool not in declared_permissions:raise ToolGuardError("tool is not declared by Skill")
  if role in {"tester","inspector"} and tool in {"workspace.write","data.delete"}:raise ToolGuardError(f"{role} cannot invoke mutating tools")
  if tool in self.HIGH_RISK and tool not in explicit_grants:raise ToolGuardError("high-risk tool requires explicit grant")
 def sanitize(self,value:Any,*,depth:int=0)->Any:
  if isinstance(depth,bool) or not isinstance(depth,int) or depth<0:raise ToolGuardError("tool input depth is invalid")
  if depth>12:raise ToolGuardError("tool input nesting is too deep")
  if isinstance(value,str):
   if len(value)>100000 or "\x00" in value:raise ToolGuardError("tool input string is invalid")
   if ".." in value.replace("\\","/").split("/"):raise ToolGuardError("tool input contains path traversal")
   return value
  if isinstance(value,Mapping):
   if len(value)>1000:raise ToolGuardError("tool input object is too large")
   if any(not isinstance(key,str) or not key for key in value):raise ToolGuardError("tool input keys must be non-empty strings")
   if any(key in {"__proto__","constructor","prototype"} for key in value):raise ToolGuardError("tool input contains forbidden keys")
   return {k:self.sanitize(v,depth=depth+1) for k,v in value.items()}
  if isinstance(value,(list,tuple)):
   if len(value)>10000:raise ToolGuardError("tool input array is too large")
   return [self.sanitize(v,depth=depth+1) for v in value]
  if value is None or isinstance(value,(bool,int)):return value
  if isinstance(value,float):
   if not math.isfinite(value):raise ToolGuardError("tool input number is invalid")
   return value
  raise ToolGuardError("tool input type is unsupported")
 def redact(self,value:Any)->Any:
  if isinstance(value,Mapping):
   if any(not isinstance(key,str) or not key for key in value):raise ToolGuardError("tool output keys must be non-empty strings")
   return {k:("[REDACTED]" if any(word in k.lower() for word in self.SECRET_KEYS) else self.redact(v)) for k,v in value.items()}
  if isinstance(value,(list,tuple)):return [self.redact(v) for v in value]
  if isinstance(value,str):return re.sub(r"(?i)(bearer\s+|sk-[A-Za-z0-9_-]{8,})\S*","[REDACTED]",value)
  if value is None or isinstance(value,(bool,int)):return value
  if isinstance(value,float):
   if not math.isfinite(value):raise ToolGuardError("tool output number is invalid")
   return value
  raise ToolGuardError("tool output type is unsupported")
