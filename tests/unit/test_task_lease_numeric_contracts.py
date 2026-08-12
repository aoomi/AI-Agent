from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_agent_queue import TaskLeaseError, TaskLeaseRepository


class TaskLeaseNumericContractTest(unittest.TestCase):
    def test_ttl_rejects_boolean_and_non_numeric_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            leases=TaskLeaseRepository(Path(directory)/"leases.db")
            for ttl in (True,"30"):
                with self.subTest(ttl=ttl),self.assertRaises(TaskLeaseError):
                    leases.acquire("job","owner",ttl=ttl)  # type: ignore[arg-type]
            lease=leases.acquire("job","owner",ttl=30)
            for ttl in (True,"30"):
                with self.subTest(renew_ttl=ttl),self.assertRaisesRegex(TaskLeaseError,"renewal"):
                    leases.renew("job","owner",lease["generation"],ttl=ttl)  # type: ignore[arg-type]


if __name__=="__main__":unittest.main()
