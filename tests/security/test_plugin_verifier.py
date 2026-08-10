import tempfile,unittest
from hashlib import sha256
from pathlib import Path
from ai_agent_security import PluginInstallVerifier,PluginVerificationError,PluginVerificationRequest
class Signatures:
 def __init__(self,valid=True):self.valid=valid
 def verify(self,**kwargs):return self.valid
class PluginInstallVerifierTest(unittest.TestCase):
 def request(self,path,content=b"package",permissions=("workspace.read",)):
  manifest=b"manifest";return PluginVerificationRequest("p",path,sha256(content).hexdigest(),manifest,sha256(manifest).hexdigest(),"ed25519","key","sig","1.0.0",permissions)
 def test_valid_package_passes_all_gates(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"p.zip";path.write_bytes(b"package");PluginInstallVerifier(Signatures(),platform_version="1.1.0",allowed_permissions=frozenset({"workspace.read"})).verify(self.request(path))
 def test_tamper_signature_version_and_permission_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"p.zip";path.write_bytes(b"tampered");verifier=PluginInstallVerifier(Signatures(),platform_version="1.0.0",allowed_permissions=frozenset({"workspace.read"}))
   with self.assertRaisesRegex(PluginVerificationError,"integrity"):verifier.verify(self.request(path))
   path.write_bytes(b"package")
   with self.assertRaisesRegex(PluginVerificationError,"signature"):PluginInstallVerifier(Signatures(False),platform_version="1.0.0",allowed_permissions=frozenset({"workspace.read"})).verify(self.request(path))
   with self.assertRaisesRegex(PluginVerificationError,"permissions"):verifier.verify(self.request(path,permissions=("network.admin",)))
if __name__=="__main__":unittest.main()
