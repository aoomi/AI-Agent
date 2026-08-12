from __future__ import annotations

import unittest

from ai_agent_tenant import IdentityContext, IdentityContextError


class IdentityContextTest(unittest.TestCase):
    def test_context_preserves_required_scope(self) -> None:
        context = IdentityContext(
            request_id="request-1",
            trace_id="trace-1",
            identity_id="identity-1",
            identity_kind="user",
            tenant_id="tenant-default",
        )
        self.assertEqual(
            context.event_scope(),
            {
                "request_id": "request-1",
                "trace_id": "trace-1",
                "identity_id": "identity-1",
                "tenant_id": "tenant-default",
            },
        )

    def test_empty_required_scope_is_rejected(self) -> None:
        with self.assertRaisesRegex(IdentityContextError, "identity_id"):
            IdentityContext("request-1", "trace-1", " ", "user", "tenant-default")

    def test_unknown_identity_kind_is_rejected(self) -> None:
        with self.assertRaisesRegex(IdentityContextError, "not supported"):
            IdentityContext("request-1", "trace-1", "identity-1", "guest", "tenant-default")

    def test_cross_tenant_scope_is_rejected(self) -> None:
        context = IdentityContext("request-1", "trace-1", "identity-1", "user", "tenant-a")
        with self.assertRaisesRegex(IdentityContextError, "tenant scope mismatch"):
            context.require_tenant("tenant-b")

    def test_runtime_identity_types_are_rejected(self) -> None:
        for values in ((1,"trace","identity","user","tenant"),("request","trace","identity",1,"tenant")):
            with self.subTest(values=values),self.assertRaises(IdentityContextError):IdentityContext(*values)
        context=IdentityContext("request","trace","identity","user","tenant")
        with self.assertRaises(IdentityContextError):context.require_tenant(1)


if __name__ == "__main__":
    unittest.main()
