from pathlib import Path

import pytest

from short_drama_workflows.production_ledger import ProductionLedger, ProductionLedgerError
from short_drama_workflows.production_orchestrator import ProductionOrchestrator


@pytest.mark.parametrize(
    ("factory", "error", "message"),
    [
        (ProductionLedger, ProductionLedgerError, "production ledger database must be a Path"),
        (ProductionOrchestrator, ValueError, "production orchestrator database must be a Path"),
    ],
)
def test_production_databases_reject_non_path_before_filesystem_side_effects(tmp_path, factory, error, message):
    target = tmp_path / "authority.sqlite"
    with pytest.raises(error, match=message):
        factory(str(target))
    assert not target.exists()
