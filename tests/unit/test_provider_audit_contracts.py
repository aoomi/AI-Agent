from __future__ import annotations

import unittest

from ai_agent_events import ProviderAuditError, ProviderAuditLedger


class ProviderAuditContractTest(unittest.TestCase):
    def _record(self, **changes):
        values = dict(tenant_id="tenant", user_id="user", project_id="project", provider_id="provider",
                      capability="video", request={"prompt": "safe"}, input_tokens=0, output_tokens=0,
                      duration_ms=1, cost_microunits=0)
        values.update(changes)
        return ProviderAuditLedger().record(**values)

    def test_record_rejects_invalid_runtime_metrics_and_request(self) -> None:
        for value in (True, 1.5, -1):
            with self.subTest(value=value), self.assertRaisesRegex(ProviderAuditError, "non-negative integers"):
                self._record(duration_ms=value)
        with self.assertRaisesRegex(ProviderAuditError, "must be a mapping"):
            self._record(request=["unsafe"])

    def test_record_rejects_unaligned_or_empty_artifact_proof(self) -> None:
        with self.assertRaisesRegex(ProviderAuditError, "must align"):
            self._record(artifact_ids=("asset-1",), artifact_checksums=())
        with self.assertRaisesRegex(ProviderAuditError, "are required"):
            self._record(artifact_ids=(" ",), artifact_checksums=("sha256",))

    def test_request_hash_rejects_non_standard_json(self) -> None:
        for request in ({"value":float("nan")},{"value":object()}):
            with self.subTest(request=request), self.assertRaisesRegex(ProviderAuditError, "standard JSON"):
                self._record(request=request)

    def test_request_hash_rejects_non_string_and_empty_keys(self) -> None:
        for request in ({1:"value"},{"nested":{1:"value"}},{" ":"value"}):
            with self.subTest(request=request),self.assertRaisesRegex(ProviderAuditError,"invalid fields"):
                self._record(request=request)


if __name__ == "__main__":
    unittest.main()
