from __future__ import annotations

import unittest

from ai_agent_security import PluginInstallVerifier,PluginVerificationError


class PluginVerifierContractTest(unittest.TestCase):
 def test_constructor_rejects_bad_verifier_version_and_permissions(self):
  for build in (lambda:PluginInstallVerifier(object(),platform_version="1.0.0",allowed_permissions=frozenset()),lambda:PluginInstallVerifier(type("V",(),{"verify":lambda *_args,**_kwargs:True})(),platform_version="1.0",allowed_permissions=frozenset()),lambda:PluginInstallVerifier(type("V",(),{"verify":lambda *_args,**_kwargs:True})(),platform_version="1.0.0",allowed_permissions=frozenset({" "}))):
   with self.subTest(build=build),self.assertRaises(PluginVerificationError):build()

if __name__=="__main__":unittest.main()
