from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "shared/contracts/agent-configuration.schema.json").read_text())


def validate(name: str, value: dict) -> list:
    validator = Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": SCHEMA["$defs"]}, format_checker=FormatChecker())
    return list(validator.iter_errors(value))


class AgentConfigurationContractTest(unittest.TestCase):
    def test_inspector_configuration_is_always_read_only(self) -> None:
        value = {
            "configuration_id": "config-1", "configuration_version": 1, "agent_id": "agent-1",
            "skill_id": "system_inspector", "role": "inspector", "model_id": "model-1",
            "system_prompt_version": "1.0", "settings": {}, "writable": False,
            "updated_by_identity_id": "user-1", "updated_at": "2026-08-07T12:00:00Z", "contract_version": "1.0",
        }
        self.assertFalse(validate("configuration", value))
        self.assertTrue(validate("configuration", {**value, "writable": True}))

    def test_valid_agent_configuration_contracts(self) -> None:
        cases = [
            ("model", {"model_id": "model-1", "provider_id": "provider-1", "display_name": "Reasoner", "capabilities": ["chat", "tool_calling"], "enabled": True, "context_window": 128000, "contract_version": "1.0"}),
            ("message", {"message_id": "message-1", "session_id": "session-1", "agent_id": "agent-1", "role": "user", "content": "配置开发智能体", "created_at": "2026-08-07T12:00:00Z", "contract_version": "1.0"}),
            ("proposal", {"proposal_id": "proposal-1", "session_id": "session-1", "agent_id": "agent-1", "proposal_type": "configuration_change", "status": "pending_confirmation", "requested_changes": {"model_id": "model-2"}, "requires_confirmation": True, "created_at": "2026-08-07T12:00:00Z", "contract_version": "1.0"}),
        ]
        for name, value in cases:
            with self.subTest(contract=name):
                self.assertFalse(validate(name, value))


if __name__ == "__main__":
    unittest.main()
