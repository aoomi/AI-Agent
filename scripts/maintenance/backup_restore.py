#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,tarfile
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
def backup(source:Path,output:Path):
 source=source.resolve();output=output.resolve()
 if not source.is_dir() or source==Path("/"):raise SystemExit("INVALID_BACKUP_SOURCE")
 output.parent.mkdir(parents=True,exist_ok=True)
 with tarfile.open(output,"w:gz") as archive:
  for name in ("config","database","assets","audit","checkpoints"):
   path=source/name
   if path.exists():archive.add(path,arcname=name,recursive=True)
 digest=sha256(output.read_bytes()).hexdigest();manifest={"archive":output.name,"sha256":digest,"created_at":datetime.now(timezone.utc).isoformat()};output.with_suffix(output.suffix+".manifest.json").write_text(json.dumps(manifest,sort_keys=True));return manifest
def restore(archive:Path,target:Path,manifest:Path):
 archive=archive.resolve();target=target.resolve();expected=json.loads(manifest.read_text())["sha256"]
 if sha256(archive.read_bytes()).hexdigest()!=expected:raise SystemExit("BACKUP_CHECKSUM_MISMATCH")
 if target.exists() and any(target.iterdir()):raise SystemExit("RESTORE_TARGET_NOT_EMPTY")
 target.mkdir(parents=True,exist_ok=True)
 with tarfile.open(archive,"r:gz") as package:
  for member in package.getmembers():
   if not (target/member.name).resolve().is_relative_to(target):raise SystemExit("UNSAFE_BACKUP_ARCHIVE")
  package.extractall(target,filter="data")
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest="action",required=True);b=sub.add_parser("backup");b.add_argument("source",type=Path);b.add_argument("output",type=Path);r=sub.add_parser("restore");r.add_argument("archive",type=Path);r.add_argument("target",type=Path);r.add_argument("manifest",type=Path);a=p.parse_args();backup(a.source,a.output) if a.action=="backup" else restore(a.archive,a.target,a.manifest)
if __name__=="__main__":main()
