"""Validate and register industry process Skill manifests."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
import re,yaml
class IndustrySkillRegistryError(ValueError):pass
@dataclass(frozen=True,slots=True)
class IndustrySkillDefinition:
 skill_id:str;name:str;industry_id:str;process_id:str;entrypoint:str;required_capabilities:frozenset[str];permissions:frozenset[str];manifest_path:Path
 @property
 def metadata(self):return {"agent_role":"developer","permissions":list(self.permissions),"required_model_capabilities":list(self.required_capabilities),"system_prompt_version":"1.0"}
class IndustrySkillRegistry:
 def __init__(self,plugins_root:Path):self.root=plugins_root.resolve();self._skills={};self._lock=RLock()
 def scan(self)->tuple[IndustrySkillDefinition,...]:
  found={}
  for path in sorted(self.root.glob("**/industry-skills/*.yaml")):
   data=yaml.safe_load(path.read_text())
   if not isinstance(data,dict) or not isinstance(data.get("skills"),list):raise IndustrySkillRegistryError(f"invalid industry manifest: {path}")
   industry=str(data.get("industry_id","")).strip()
   for raw in data["skills"]:
    item=self._parse(industry,raw,path)
    if item.skill_id in found:raise IndustrySkillRegistryError(f"duplicate industry skill: {item.skill_id}")
    found[item.skill_id]=item
  with self._lock:self._skills=found;return tuple(found[key] for key in sorted(found))
 def get(self,skill_id:str)->IndustrySkillDefinition:
  with self._lock:
   try:return self._skills[skill_id]
   except KeyError as error:raise IndustrySkillRegistryError("industry skill is not registered") from error
 @staticmethod
 def _parse(industry,raw,path):
  if not industry or not isinstance(raw,dict):raise IndustrySkillRegistryError("industry skill manifest is invalid")
  values=[str(raw.get(key,"")).strip() for key in ("skill_id","name","process_id","entrypoint")];caps=raw.get("required_capabilities");permissions=raw.get("permissions",[])
  if not all(values) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}",values[0]) or Path(values[3]).is_absolute() or ".." in Path(values[3]).parts or not isinstance(caps,list) or not caps or not isinstance(permissions,list):raise IndustrySkillRegistryError("industry skill manifest fields are invalid")
  return IndustrySkillDefinition(values[0],values[1],industry,values[2],values[3],frozenset(caps),frozenset(permissions),path)
