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
 def __init__(self,plugins_root:Path):
  if not isinstance(plugins_root,Path):raise IndustrySkillRegistryError("plugins root must be a Path")
  self.root=plugins_root.resolve();self._skills={};self._lock=RLock()
 def scan(self)->tuple[IndustrySkillDefinition,...]:
  found={}
  for path in sorted(self.root.glob("**/industry-skills/*.yaml")):
   data=yaml.safe_load(path.read_text())
   if not isinstance(data,dict) or not isinstance(data.get("skills"),list):raise IndustrySkillRegistryError(f"invalid industry manifest: {path}")
   raw_industry=data.get("industry_id","")
   if not isinstance(raw_industry,str):raise IndustrySkillRegistryError(f"invalid industry manifest: {path}")
   industry=raw_industry.strip()
   for raw in data["skills"]:
    item=self._parse(industry,raw,path)
    if item.skill_id in found:raise IndustrySkillRegistryError(f"duplicate industry skill: {item.skill_id}")
    found[item.skill_id]=item
  with self._lock:self._skills=found;return tuple(found[key] for key in sorted(found))
 def get(self,skill_id:str)->IndustrySkillDefinition:
  if not isinstance(skill_id,str):raise IndustrySkillRegistryError("industry skill_id is required")
  skill_id=skill_id.strip()
  if not skill_id:raise IndustrySkillRegistryError("industry skill_id is required")
  with self._lock:
   try:return self._skills[skill_id]
   except KeyError as error:raise IndustrySkillRegistryError("industry skill is not registered") from error
 @staticmethod
 def _parse(industry,raw,path):
  if not isinstance(industry,str) or not industry.strip() or not isinstance(raw,dict) or not isinstance(path,Path):raise IndustrySkillRegistryError("industry skill manifest is invalid")
  source=[raw.get(key,"") for key in ("skill_id","name","process_id","entrypoint")]
  if any(not isinstance(value,str) for value in source):raise IndustrySkillRegistryError("industry skill manifest fields are invalid")
  values=[value.strip() for value in source];caps=raw.get("required_capabilities");permissions=raw.get("permissions",[])
  if (not all(values) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}",values[0])
      or Path(values[3]).is_absolute() or ".." in Path(values[3]).parts
      or not isinstance(caps,list) or not caps or any(not isinstance(value,str) or not value.strip() for value in caps)
      or not isinstance(permissions,list) or any(not isinstance(value,str) or not value.strip() for value in permissions)):
   raise IndustrySkillRegistryError("industry skill manifest fields are invalid")
  return IndustrySkillDefinition(values[0],values[1],industry,values[2],values[3],frozenset(value.strip() for value in caps),frozenset(value.strip() for value in permissions),path)
