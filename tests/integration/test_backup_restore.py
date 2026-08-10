import tempfile,unittest
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
if __name__=="__main__":unittest.main()
