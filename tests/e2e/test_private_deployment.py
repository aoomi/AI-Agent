import json,unittest
from pathlib import Path
class PrivateDeploymentE2ETest(unittest.TestCase):
 def test_install_artifacts_alerts_backup_and_rollback_are_present(self):
  root=Path(__file__).resolve().parents[2]
  for path in ("deploy/docker/Dockerfile","deploy/docker/compose.private.yaml","deploy/environments/private-production.env.example","deploy/alert-rules.yaml","scripts/deploy/install_private.py","scripts/maintenance/backup_restore.py","scripts/migration/release_manager.py"):self.assertTrue((root/path).is_file(),path)
  self.assertTrue(json.loads((root/"deploy/release-policy.json").read_text())["automatic_rollback_on_health_failure"])
if __name__=="__main__":unittest.main()
