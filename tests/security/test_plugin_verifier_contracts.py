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

if __name__=="__main__":unittest.main()
