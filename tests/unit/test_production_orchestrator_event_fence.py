from __future__ import annotations

from pathlib import Path
import tempfile

from plugins.builtin.short_drama.workflows.production_orchestrator import ProductionOrchestrator


IDENTITY = {"tenant_id": "tenant-a", "user_id": "user-a", "project_id": "project-a"}


def test_rejected_projection_revision_does_not_replace_authoritative_event() -> None:
    with tempfile.TemporaryDirectory() as directory:
        brain = ProductionOrchestrator(Path(directory) / "graph.sqlite")
        brain.report(IDENTITY, "requirements", "completed", trusted=True)
        accepted = brain.report(
            IDENTITY,
            "outline",
            "pending_confirmation",
            projection_revision=8,
            evidence={"version": "current"},
        )
        rejected = brain.report(
            IDENTITY,
            "outline",
            "failed",
            projection_revision=7,
            error="late old projector",
        )

        assert rejected["stages"]["outline"] == "pending_confirmation"
        assert rejected["event"] == accepted["event"]
        assert rejected["event"]["evidence"] == {"version": "current"}


def test_rejected_stage_generation_does_not_replace_event_after_sqlite_reload() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "graph.sqlite"
        brain = ProductionOrchestrator(database)
        brain.report(IDENTITY, "requirements", "completed", trusted=True)
        accepted = brain.report(
            IDENTITY,
            "outline",
            "running",
            stage_generation=4,
            request_id="current-owner",
        )
        rejected = brain.report(
            IDENTITY,
            "outline",
            "cancelled",
            stage_generation=3,
            request_id="expired-owner",
        )
        assert rejected["stages"]["outline"] == "running"
        assert rejected["event"] == accepted["event"]
        brain.connection.close()

        reloaded = ProductionOrchestrator(database).state(IDENTITY)
        assert reloaded["stages"]["outline"] == "running"
        assert reloaded["event"] == accepted["event"]


def test_unfenced_event_cannot_overwrite_a_fenced_stage_generation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        brain = ProductionOrchestrator(Path(directory) / "graph.sqlite")
        brain.report(IDENTITY, "requirements", "completed", trusted=True)
        accepted = brain.report(
            IDENTITY,
            "outline",
            "running",
            stage_generation=5,
            request_id="leased-owner",
        )
        rejected = brain.report(IDENTITY, "outline", "failed", error="unfenced legacy callback")

        assert rejected["stages"]["outline"] == "running"
        assert rejected["stage_generations"]["outline"] == 5
        assert rejected["event"] == accepted["event"]


def test_higher_generation_accepts_a_fresh_lower_revision() -> None:
    with tempfile.TemporaryDirectory() as directory:
        brain = ProductionOrchestrator(Path(directory) / "graph.sqlite")
        brain.report(IDENTITY, "requirements", "completed", trusted=True)
        brain.report(
            IDENTITY, "outline", "running",
            stage_generation=4, projection_revision=10, request_id="old-owner",
        )
        accepted = brain.report(
            IDENTITY, "outline", "pending_confirmation",
            stage_generation=5, projection_revision=1, request_id="new-owner",
        )

        assert accepted["stages"]["outline"] == "pending_confirmation"
        assert accepted["stage_generations"]["outline"] == 5
        assert accepted["projection_revisions"]["outline"] == 1
        assert accepted["event"]["request_id"] == "new-owner"


def test_higher_generation_revision_zero_is_accepted_once_then_strictly_fenced() -> None:
    with tempfile.TemporaryDirectory() as directory:
        brain = ProductionOrchestrator(Path(directory) / "graph.sqlite")
        brain.report(IDENTITY, "requirements", "completed", trusted=True)
        brain.report(
            IDENTITY, "outline", "running",
            stage_generation=4, projection_revision=10, request_id="old-owner",
        )
        accepted = brain.report(
            IDENTITY, "outline", "pending_confirmation",
            stage_generation=5, projection_revision=0, request_id="new-owner-r0",
        )
        duplicate = brain.report(
            IDENTITY, "outline", "failed",
            stage_generation=5, projection_revision=0, request_id="duplicate-r0",
        )
        missing = brain.report(
            IDENTITY, "outline", "cancelled",
            stage_generation=5, request_id="missing-r0",
        )
        advanced = brain.report(
            IDENTITY, "outline", "pending_confirmation",
            stage_generation=5, projection_revision=1, request_id="new-owner-r1",
        )

        assert accepted["projection_revisions"]["outline"] == 0
        assert duplicate["event"] == accepted["event"]
        assert missing["event"] == accepted["event"]
        assert duplicate["stages"]["outline"] == "pending_confirmation"
        assert missing["stages"]["outline"] == "pending_confirmation"
        assert advanced["event"]["request_id"] == "new-owner-r1"
        assert advanced["projection_revisions"]["outline"] == 1


def test_legacy_checkpoint_without_stage_events_can_migrate_once() -> None:
    with tempfile.TemporaryDirectory() as directory:
        brain = ProductionOrchestrator(Path(directory) / "graph.sqlite")
        brain.report(IDENTITY, "requirements", "completed", trusted=True)
        brain.report(
            IDENTITY, "outline", "running",
            stage_generation=5, projection_revision=0, request_id="first-current-event",
        )
        # Simulate a checkpoint written before accepted per-stage events were
        # introduced. The first current-owner event establishes the new map;
        # subsequent zero-revision repeats are fenced by the normal path.
        config = {"configurable": {"thread_id": brain.thread_id(**IDENTITY)}}
        with brain._lock:
            brain.graph.update_state(config, {"stage_events": {"outline": None}})
        migrated = brain.report(
            IDENTITY, "outline", "pending_confirmation",
            stage_generation=5, request_id="migration-event",
        )
        rejected = brain.report(
            IDENTITY, "outline", "failed",
            stage_generation=5, request_id="post-migration-repeat",
        )

        assert migrated["event"]["request_id"] == "migration-event"
        assert rejected["event"] == migrated["event"]


def test_revision_is_monotonic_within_the_same_generation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        brain = ProductionOrchestrator(Path(directory) / "graph.sqlite")
        brain.report(IDENTITY, "requirements", "completed", trusted=True)
        brain.report(
            IDENTITY, "outline", "running",
            stage_generation=6, projection_revision=2, request_id="current-r2",
        )
        accepted = brain.report(
            IDENTITY, "outline", "pending_confirmation",
            stage_generation=6, projection_revision=3, request_id="current-r3",
        )
        rejected_lower = brain.report(
            IDENTITY, "outline", "failed",
            stage_generation=6, projection_revision=2, request_id="late-r2",
        )
        rejected_missing = brain.report(
            IDENTITY, "outline", "cancelled",
            stage_generation=6, request_id="missing-revision",
        )

        assert accepted["projection_revisions"]["outline"] == 3
        assert rejected_lower["event"] == accepted["event"]
        assert rejected_missing["event"] == accepted["event"]


def test_two_instances_converge_on_the_highest_generation_after_reload() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "graph.sqlite"
        first = ProductionOrchestrator(database)
        second = ProductionOrchestrator(database)
        first.report(IDENTITY, "requirements", "completed", trusted=True)
        first.report(
            IDENTITY, "outline", "running",
            stage_generation=8, projection_revision=20, request_id="instance-one-old",
        )
        accepted = second.report(
            IDENTITY, "outline", "pending_confirmation",
            stage_generation=9, projection_revision=1, request_id="instance-two-new",
        )
        rejected = first.report(
            IDENTITY, "outline", "failed",
            stage_generation=8, projection_revision=21, request_id="instance-one-late",
        )

        assert rejected["event"] == accepted["event"]
        assert rejected["stage_generations"]["outline"] == 9
        first.connection.close(); second.connection.close()
        reloaded = ProductionOrchestrator(database).state(IDENTITY)
        assert reloaded["stage_generations"]["outline"] == 9
        assert reloaded["projection_revisions"]["outline"] == 1
        assert reloaded["event"]["request_id"] == "instance-two-new"


def test_rejected_event_for_older_stage_restores_latest_cross_stage_event() -> None:
    with tempfile.TemporaryDirectory() as directory:
        brain = ProductionOrchestrator(Path(directory) / "graph.sqlite")
        brain.report(IDENTITY, "requirements", "completed", trusted=True)
        brain.report(IDENTITY, "outline", "completed", trusted=True, projection_revision=3)
        accepted = brain.report(
            IDENTITY,
            "script",
            "running",
            projection_revision=9,
            stage_generation=2,
            request_id="script-owner",
        )
        rejected = brain.report(
            IDENTITY,
            "outline",
            "failed",
            projection_revision=2,
            error="late outline projection",
        )

        assert rejected["current_stage"] == "script"
        assert rejected["event"] == accepted["event"]
        assert rejected["decision"]["stage"] == "script"
