from __future__ import annotations

import unittest
from pathlib import Path

from ai_agent_discovery import IndustrySkillRegistry, IndustrySkillRegistryError


class IndustrySkillManifestContractTest(unittest.TestCase):
    def test_parse_rejects_non_string_or_empty_capability_and_permission(self) -> None:
        base={"skill_id":"skill","name":"Skill","process_id":"process","entrypoint":"main.py",
              "required_capabilities":["chat"],"permissions":["workspace.read"]}
        for changes in ({"required_capabilities":[1]},{"required_capabilities":[" "]},{"permissions":[1]},{"permissions":[" "]}):
            raw={**base,**changes}
            with self.subTest(raw=raw),self.assertRaisesRegex(IndustrySkillRegistryError,"fields are invalid"):
                IndustrySkillRegistry._parse("industry",raw,Path("manifest.yaml"))


if __name__=="__main__":unittest.main()
