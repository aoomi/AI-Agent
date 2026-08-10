import unittest
from short_drama_backend.lora_selection import LoraDefinition,LoraSelectionError,LoraSelectionService
class LoraSelectionTest(unittest.TestCase):
 def setUp(self):self.service=LoraSelectionService((LoraDefinition("cn-mythic","1.0",frozenset({"神话古风"}),"神话"),LoraDefinition("cn-romance","2.0",frozenset({"都市甜宠"}),"甜宠")))
 def test_automatic_is_deterministic_and_project_locked(self):
  first=self.service.select("t","p","都市甜宠");second=self.service.select("t","p","神话古风");self.assertEqual(first.selected_lora_id,"cn-romance");self.assertEqual(second,first);self.assertTrue(first.locked)
 def test_manual_override_and_seeded_exploration(self):
  manual=self.service.select("t","p","神话古风",mode="manual",lora_id="cn-romance",override=True);self.assertEqual(manual.selected_lora_id,"cn-romance")
  one=self.service.select("t","explore","神话古风",mode="exploration",exploration_seed=7);two=self.service.select("t","explore","神话古风",mode="exploration",exploration_seed=7);self.assertEqual(one,two);self.assertFalse(one.locked)
  with self.assertRaisesRegex(LoraSelectionError,"requires seed"):self.service.select("t","x","神话古风",mode="exploration")
if __name__=="__main__":unittest.main()
