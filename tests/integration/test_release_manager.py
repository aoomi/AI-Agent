import tempfile,unittest
from pathlib import Path
from scripts.migration.release_manager import ReleaseError,ReleaseManager
class ReleaseManagerTest(unittest.TestCase):
 def test_atomic_upgrade_and_rollback(self):
  with tempfile.TemporaryDirectory() as d:
   m=ReleaseManager(Path(d));m.prepare("0.0.0","0.1.0",{"version":"0.1.0"});m.activate("0.1.0");m.prepare("0.1.0","0.2.0",{"version":"0.2.0"});m.activate("0.2.0");self.assertEqual((Path(d)/"current").resolve().name,"0.2.0");m.rollback();self.assertEqual((Path(d)/"current").resolve().name,"0.1.0")
 def test_incompatible_upgrade_fails(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ReleaseError):ReleaseManager(Path(d)).prepare("1.0.0","3.0.0",{})
if __name__=="__main__":unittest.main()
