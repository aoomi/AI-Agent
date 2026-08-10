from __future__ import annotations

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
import yaml


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = ROOT / "plugins/builtin/short_drama"


class ShortDramaManifestTest(unittest.TestCase):
    def test_manifest_matches_shared_contract_and_entries_exist(self) -> None:
        manifest = yaml.safe_load((PLUGIN_ROOT / "manifests/plugin.yaml").read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "shared/contracts/domain.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator({"$ref": "#/$defs/plugin_manifest", "$defs": schema["$defs"]}).validate(manifest)
        self.assertTrue((PLUGIN_ROOT / manifest["backend_entry"]).is_file())
        self.assertTrue((PLUGIN_ROOT / manifest["migration_entry"]).is_file())


if __name__ == "__main__": unittest.main()
