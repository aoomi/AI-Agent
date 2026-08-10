#!/usr/bin/env python3
"""Atomic release activation, compatibility validation and rollback."""
from __future__ import annotations
import argparse,json,os,re
from pathlib import Path
class ReleaseError(ValueError):pass
def compatible(current:str,target:str)->bool:
 def v(x):
  if not re.fullmatch(r"\d+\.\d+\.\d+",x):raise ReleaseError("release version is invalid")
  return tuple(map(int,x.split(".")))
 a,b=v(current),v(target);return b[0] in {a[0],a[0]+1} and b>a
class ReleaseManager:
 def __init__(self,root:Path):self.root=root.resolve();self.releases=self.root/"releases";self.releases.mkdir(parents=True,exist_ok=True)
 def prepare(self,current:str,target:str,metadata:dict)->Path:
  if not compatible(current,target):raise ReleaseError("release is incompatible")
  path=self.releases/target;path.mkdir();(path/"release.json").write_text(json.dumps(metadata,sort_keys=True));return path
 def activate(self,version:str)->None:
  target=self.releases/version
  if not (target/"release.json").exists():raise ReleaseError("release is not prepared")
  current=self.root/"current";previous=self.root/"previous";old=os.readlink(current) if current.is_symlink() else None
  temporary=self.root/"current.next";temporary.unlink(missing_ok=True);temporary.symlink_to(target)
  temporary.replace(current)
  if old:previous.unlink(missing_ok=True);previous.symlink_to(old)
 def rollback(self)->None:
  previous=self.root/"previous"
  if not previous.is_symlink():raise ReleaseError("previous release does not exist")
  target=previous.resolve();temporary=self.root/"current.rollback";temporary.symlink_to(target);temporary.replace(self.root/"current")
def main():
 p=argparse.ArgumentParser();p.add_argument("root",type=Path);p.add_argument("action",choices=("activate","rollback"));p.add_argument("--version");a=p.parse_args();manager=ReleaseManager(a.root);manager.activate(a.version) if a.action=="activate" and a.version else manager.rollback()
if __name__=="__main__":main()
