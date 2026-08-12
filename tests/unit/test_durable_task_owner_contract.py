from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ai_agent_queue import DurableTaskRepository


def owned(status="queued"):
    return {"status": status, "tenant_id": "tenant", "user_id": "user", "project_id": "project"}


def test_durable_tasks_require_full_owner_scope_and_immutable_task_class():
    with TemporaryDirectory() as directory:
        repository = DurableTaskRepository(Path(directory) / "tasks.sqlite")
        for job in ({"status": "queued"}, {"tenant_id": "tenant", "user_id": "user", "status": "queued"}):
            with pytest.raises(ValueError, match="owner scope"):
                repository.upsert("job", "text", job)
        repository.upsert("job", "text", owned())
        with pytest.raises(ValueError, match="another task class"):
            repository.upsert("job", "video", owned("completed"))
        assert repository.get("job", tenant_id="tenant", user_id="user", project_id="project")["task_class"] == "text"
        assert repository.get("job", tenant_id="tenant", user_id="other", project_id="project") is None


def test_single_upsert_executes_exactly_once():
    with TemporaryDirectory() as directory:
        repository = DurableTaskRepository(Path(directory) / "tasks.sqlite")
        calls = 0
        original = repository._execute_upsert

        def count(connection, values):
            nonlocal calls
            calls += 1
            return original(connection, values)

        repository._execute_upsert = count
        repository.upsert("job", "text", owned())
        assert calls == 1
