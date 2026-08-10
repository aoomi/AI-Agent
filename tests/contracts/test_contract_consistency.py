from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "shared/contracts/domain.contract.ts").read_text(encoding="utf-8")
SCHEMA = json.loads((ROOT / "shared/contracts/domain.schema.json").read_text(encoding="utf-8"))
OPENAPI = yaml.safe_load((ROOT / "docs/contracts/openapi.yaml").read_text(encoding="utf-8"))


def source_values(constant_name: str) -> list[str]:
    match = re.search(
        rf"export const {re.escape(constant_name)}\s*=\s*\[(.*?)\]\s*as const;",
        SOURCE,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"missing TypeScript constant: {constant_name}")
    return re.findall(r'"([^"]+)"', match.group(1))


class ContractConsistencyTest(unittest.TestCase):
    def assert_enum_equal(self, constant_name: str, schema_values: list[str]) -> None:
        self.assertEqual(source_values(constant_name), schema_values)

    def test_domain_status_enums_match_runtime_schema(self) -> None:
        definitions = SCHEMA["$defs"]
        self.assert_enum_equal("identityKinds", definitions["identity"]["properties"]["identity_kind"]["enum"])
        self.assert_enum_equal("tenantStatuses", definitions["tenant"]["properties"]["status"]["enum"])
        self.assert_enum_equal("projectStatuses", definitions["project"]["properties"]["status"]["enum"])
        self.assert_enum_equal("taskStatuses", definitions["task"]["properties"]["status"]["enum"])
        self.assert_enum_equal("pluginStatuses", definitions["plugin"]["properties"]["status"]["enum"])
        self.assert_enum_equal("assetStatuses", definitions["asset"]["properties"]["status"]["enum"])

    def test_transition_enums_match_runtime_schema(self) -> None:
        definitions = SCHEMA["$defs"]
        self.assert_enum_equal("projectStateTransitions", definitions["project_transition"]["properties"]["transition"]["enum"])
        self.assert_enum_equal("taskStateTransitions", definitions["task_transition"]["properties"]["transition"]["enum"])
        self.assert_enum_equal("pluginStateTransitions", definitions["plugin_transition"]["properties"]["transition"]["enum"])

    def test_security_and_event_enums_match_runtime_schema(self) -> None:
        definitions = SCHEMA["$defs"]
        self.assert_enum_equal("authorizationActions", definitions["authorization"]["oneOf"][0]["properties"]["action"]["enum"])
        self.assert_enum_equal("pluginPermissionKinds", definitions["plugin_manifest"]["properties"]["permissions"]["items"]["enum"])
        self.assert_enum_equal("errorCodes", definitions["error"]["properties"]["data"]["properties"]["error_code"]["enum"])
        self.assert_enum_equal("eventTypes", definitions["event"]["properties"]["event_type"]["enum"])

    def test_openapi_public_enums_match_shared_contracts(self) -> None:
        schemas = OPENAPI["components"]["schemas"]
        self.assertEqual(source_values("taskStatuses"), schemas["TaskReference"]["properties"]["status"]["enum"])
        self.assertEqual([400, 401, 403, 404, 409, 500], schemas["ErrorResponse"]["properties"]["code"]["enum"])
        self.assertEqual(
            set(OPENAPI["paths"]),
            {
                "/health", "/api/v1/agents/register", "/api/v1/agents/{agent_id}",
                "/api/v1/tasks", "/api/v1/tasks/{task_id}", "/api/v1/tasks/{task_id}/cancel", "/api/v1/tasks/{task_id}/resume",
                "/api/v1/models", "/api/v1/models/register", "/api/v1/agent-configurations",
                "/api/v1/agent-configurations/{agent_id}", "/api/v1/agent-configurations/{agent_id}/update", "/api/v1/agent-configurations/{agent_id}/history",
                "/api/v1/agent-conversations", "/api/v1/agent-conversations/{session_id}", "/api/v1/agent-conversations/{session_id}/messages",
                "/api/v1/agent-proposals/{proposal_id}/confirm", "/api/v1/agent-proposals/{proposal_id}/reject",
            },
        )
        self.assertEqual(source_values("taskStatuses"), schemas["Task"]["properties"]["status"]["enum"])


if __name__ == "__main__":
    unittest.main()
