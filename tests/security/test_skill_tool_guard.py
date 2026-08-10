import unittest
from ai_agent_security import SkillToolGuard,ToolGuardError
class SkillToolGuardTest(unittest.TestCase):
 def setUp(self):self.guard=SkillToolGuard()
 def test_authorization_and_high_risk_default_deny(self):
  self.guard.authorize(role="developer",tool="workspace.read",declared_permissions=frozenset({"workspace.read"}))
  with self.assertRaisesRegex(ToolGuardError,"explicit grant"):self.guard.authorize(role="developer",tool="workspace.write",declared_permissions=frozenset({"workspace.write"}))
  with self.assertRaisesRegex(ToolGuardError,"inspector"):self.guard.authorize(role="inspector",tool="workspace.write",declared_permissions=frozenset({"workspace.write"}),explicit_grants=frozenset({"workspace.write"}))
 def test_sanitizes_input_and_redacts_output(self):
  self.assertEqual(self.guard.sanitize({"prompt":"safe"}),{"prompt":"safe"})
  for value in ({"path":"../../secret"},{"__proto__":{}},{"x":"a\x00b"}):
   with self.assertRaises(ToolGuardError):self.guard.sanitize(value)
  output=self.guard.redact({"api_key":"secret","message":"Bearer abcdefghijklmnop"});self.assertEqual(output["api_key"],"[REDACTED]");self.assertNotIn("Bearer",output["message"])
if __name__=="__main__":unittest.main()
