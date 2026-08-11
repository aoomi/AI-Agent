import json,os,sqlite3,tarfile,tempfile,unittest
from hashlib import sha256
from pathlib import Path
from scripts.maintenance.backup_restore import backup,restore
class BackupRestoreTest(unittest.TestCase):
 def test_backup_and_restore_all_material_data(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/"source";(source/"database").mkdir(parents=True);(source/"database/db").write_text("state");(source/"assets").mkdir();(source/"assets/a").write_bytes(b"asset");archive=root/"backup.tar.gz";backup(source,archive);target=root/"restored";restore(archive,target,archive.with_suffix(".gz.manifest.json"));self.assertEqual((target/"database/db").read_text(),"state");self.assertEqual((target/"assets/a").read_bytes(),b"asset")
 def test_tampered_backup_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/"source";source.mkdir();archive=root/"b.tar.gz";backup(source,archive);archive.write_bytes(archive.read_bytes()+b"tamper")
   with self.assertRaises(SystemExit):restore(archive,root/"target",archive.with_suffix(".gz.manifest.json"))
 def test_sqlite_is_snapshotted_and_restored_as_a_queryable_database(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/"source";(source/"database").mkdir(parents=True);database=source/"database/state.sqlite"
   with sqlite3.connect(database) as connection:connection.execute("CREATE TABLE facts(id INTEGER PRIMARY KEY,value TEXT)");connection.execute("INSERT INTO facts(value) VALUES ('权威状态')")
   (source/"assets").mkdir();(source/"assets/media.bin").write_bytes(b"media-evidence")
   archive=root/"backup.tar.gz";manifest=backup(source,archive);target=root/"restored";restore(archive,target,archive.with_suffix(".gz.manifest.json"))
   with sqlite3.connect(target/"database/state.sqlite") as connection:self.assertEqual(connection.execute("SELECT value FROM facts").fetchone(),("权威状态",))
   self.assertEqual((target/"assets/media.bin").read_bytes(),b"media-evidence")
   self.assertEqual({item["path"] for item in manifest["files"]},{"assets/media.bin","database/state.sqlite"})
 def test_sqlite_runtime_sidecars_are_not_archived_beside_the_online_snapshot(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/"source";(source/"database").mkdir(parents=True);database=source/"database/state.sqlite"
   connection=sqlite3.connect(database);connection.execute("PRAGMA journal_mode=WAL");connection.execute("CREATE TABLE facts(value TEXT)");connection.execute("INSERT INTO facts VALUES ('live')");connection.commit()
   archive=root/"backup.tar.gz";manifest=backup(source,archive);connection.close()
   self.assertEqual([item["path"] for item in manifest["files"]],["database/state.sqlite"])
 def test_source_symlink_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/"source";(source/"config").mkdir(parents=True);outside=root/"secret";outside.write_text("secret");os.symlink(outside,source/"config/link")
   with self.assertRaisesRegex(SystemExit,"UNSAFE_BACKUP_SOURCE_ENTRY"):backup(source,root/"backup.tar.gz")
   linked_root=root/"linked-source";os.symlink(source,linked_root)
   with self.assertRaisesRegex(SystemExit,"INVALID_BACKUP_SOURCE"):backup(linked_root,root/"linked.tar.gz")
 def test_archive_links_and_manifest_inventory_tampering_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);archive=root/"unsafe.tar.gz"
   with tarfile.open(archive,"w:gz") as package:
    link=tarfile.TarInfo("assets/link");link.type=tarfile.SYMTYPE;link.linkname="/tmp/outside";package.addfile(link)
   manifest=archive.with_suffix(".gz.manifest.json");manifest.write_text(json.dumps({"version":2,"archive":archive.name,"sha256":sha256(archive.read_bytes()).hexdigest(),"files":[]}))
   with self.assertRaisesRegex(SystemExit,"UNSAFE_BACKUP_ARCHIVE"):restore(archive,root/"target",manifest)

   source=root/"source";(source/"audit").mkdir(parents=True);(source/"audit/events.jsonl").write_text("event")
   safe=root/"safe.tar.gz";payload=backup(source,safe);payload["files"][0]["sha256"]="0"*64;safe.with_suffix(".gz.manifest.json").write_text(json.dumps(payload))
   with self.assertRaisesRegex(SystemExit,"RESTORED_CONTENT_MISMATCH"):restore(safe,root/"restored",safe.with_suffix(".gz.manifest.json"))
 def test_restore_target_symlink_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/"source";(source/"config").mkdir(parents=True);(source/"config/app.json").write_text("{}")
   archive=root/"backup.tar.gz";backup(source,archive);outside=root/"outside";outside.mkdir();target=root/"target";os.symlink(outside,target)
   with self.assertRaisesRegex(SystemExit,"UNSAFE_RESTORE_PATH"):restore(archive,target,archive.with_suffix(".gz.manifest.json"))
   self.assertEqual(list(outside.iterdir()),[])
if __name__=="__main__":unittest.main()
