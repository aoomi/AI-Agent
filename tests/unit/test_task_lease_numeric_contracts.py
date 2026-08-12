from __future__ import annotations

import tempfile
import unittest
import math
from pathlib import Path

from ai_agent_queue import TaskLeaseError, TaskLeaseRepository


class TaskLeaseNumericContractTest(unittest.TestCase):
    def test_repository_requires_path_database(self) -> None:
        with self.assertRaisesRegex(TaskLeaseError,"database must be a Path"):
            TaskLeaseRepository("leases.db")  # type: ignore[arg-type]

    def test_ttl_rejects_boolean_and_non_numeric_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            leases=TaskLeaseRepository(Path(directory)/"leases.db")
            for ttl in (True,"30",math.nan,math.inf):
                with self.subTest(ttl=ttl),self.assertRaises(TaskLeaseError):
                    leases.acquire("job","owner",ttl=ttl)  # type: ignore[arg-type]
            lease=leases.acquire("job","owner",ttl=30)
            for ttl in (True,"30",math.nan,math.inf):
                with self.subTest(renew_ttl=ttl),self.assertRaisesRegex(TaskLeaseError,"renewal"):
                    leases.renew("job","owner",lease["generation"],ttl=ttl)  # type: ignore[arg-type]

    def test_owner_generation_and_clock_contracts_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            leases=TaskLeaseRepository(Path(directory)/"leases.db")
            for operation in (
                lambda:leases.acquire(1,"owner"),lambda:leases.acquire("job",1),lambda:leases.acquire("job","owner",now=math.nan),
                lambda:leases.release("job","owner",1.5),lambda:leases.request_cancel(1),lambda:leases.request_cancel("job",now=math.inf),
                lambda:leases.reap_expired(now=True),
            ):
                with self.subTest(operation=operation),self.assertRaises(TaskLeaseError):operation()


if __name__=="__main__":unittest.main()
