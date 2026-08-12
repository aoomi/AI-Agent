from __future__ import annotations

import unittest

from ai_agent_security import SecurityAuditError, SecurityAuditLedger


class SecurityAuditRetentionContractTest(unittest.TestCase):
    def test_retention_rejects_runtime_pseudo_integers(self) -> None:
        for value in (True, 30.5, 29):
            with self.subTest(value=value), self.assertRaisesRegex(SecurityAuditError, "integer of at least 30"):
                SecurityAuditLedger(value)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
