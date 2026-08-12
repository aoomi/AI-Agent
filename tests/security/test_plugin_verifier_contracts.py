from __future__ import annotations

import unittest

from ai_agent_security import PluginInstallVerifier,PluginVerificationError,PluginVerificationRequest


class PluginVerifierContractTest(unittest.TestCase):
 def test_constructor_rejects_bad_verifier_version_and_permissions(self):
  for build in (lambda:PluginInstallVerifier(object(),platform_version="1.0.0",allowed_permissions=frozenset()),lambda:PluginInstallVerifier(type("V",(),{"verify":lambda *_args,**_kwargs:True})(),platform_version="1.0",allowed_permissions=frozenset()),lambda:PluginInstallVerifier(type("V",(),{"verify":lambda *_args,**_kwargs:True})(),platform_version="1.0.0",allowed_permissions=frozenset({" "})),lambda:PluginInstallVerifier(type("V",(),{"verify":lambda *_args,**_kwargs:True})(),platform_version="1.0.0",allowed_permissions=[])):
   with self.subTest(build=build),self.assertRaises(PluginVerificationError):build()
 def test_verify_rejects_bad_runtime_request_structure(self):
  verifier=PluginInstallVerifier(type("V",(),{"verify":lambda *_args,**_kwargs:True})(),platform_version="1.0.0",allowed_permissions=frozenset())
  for request in (object(),PluginVerificationRequest("p","path","hash",b"manifest","hash","ed25519","key","sig","1.0.0",()),PluginVerificationRequest("p",__import__("pathlib").Path("path"),"hash","manifest","hash","ed25519","key","sig","1.0.0",()),PluginVerificationRequest("p",__import__("pathlib").Path("path"),"hash",b"manifest","hash","ed25519","key","sig","1.0.0",[]),PluginVerificationRequest("p",__import__("pathlib").Path("path"),"hash",b"manifest","hash","ed25519","key","sig","1.0",())):
   with self.subTest(request=request),self.assertRaises(PluginVerificationError):verifier.verify(request)
 def test_signature_verifier_result_must_be_boolean(self):
  from hashlib import sha256
  from pathlib import Path
  from tempfile import TemporaryDirectory
  with TemporaryDirectory() as directory:
   path=Path(directory)/"plugin.zip";path.write_bytes(b"package");manifest=b"manifest"
   request=PluginVerificationRequest("p",path,sha256(b"package").hexdigest(),manifest,sha256(manifest).hexdigest(),"ed25519","key","sig","1.0.0",())
   verifier=PluginInstallVerifier(type("V",(),{"verify":lambda *_args,**_kwargs:1})(),platform_version="1.0.0",allowed_permissions=frozenset())
   with self.assertRaisesRegex(PluginVerificationError,"signature"):verifier.verify(request)

if __name__=="__main__":unittest.main()
