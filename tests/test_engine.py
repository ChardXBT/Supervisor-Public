from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supervisor_public import ProjectState, demo_engine  # noqa: E402


class SupervisorEngineTests(unittest.TestCase):
    def test_priority_and_capacity_prevent_start_storm(self) -> None:
        engine = demo_engine()
        first = engine.schedule()
        second = engine.schedule()
        self.assertEqual(first.name, "worker-alpha")
        self.assertEqual(second.name, "worker-beta")
        self.assertIsNone(engine.schedule())
        self.assertLessEqual(engine.running_weight, engine.capacity)

    def test_disconnect_pauses_without_marking_complete(self) -> None:
        engine = demo_engine()
        project = engine.schedule()
        engine.disconnect()
        self.assertEqual(project.state, ProjectState.PAUSED)
        self.assertNotEqual(project.state, ProjectState.STOPPED)

    def test_recovery_requires_explicit_release(self) -> None:
        engine = demo_engine()
        project = engine.schedule()
        engine.fail(project.name, repair_required=False)
        self.assertEqual(project.state, ProjectState.COOLDOWN)
        engine.release_cooldown(project.name)
        self.assertEqual(project.state, ProjectState.READY)

    def test_repair_required_is_not_auto_retried(self) -> None:
        engine = demo_engine()
        project = engine.schedule()
        engine.fail(project.name, repair_required=True)
        self.assertEqual(project.state, ProjectState.REPAIR_REQUIRED)
        next_project = engine.schedule()
        self.assertIsNotNone(next_project)
        self.assertNotEqual(next_project.name, project.name)

    def test_acknowledge_repair_clears_latch(self) -> None:
        engine = demo_engine()
        project = engine.schedule()
        engine.fail(project.name, repair_required=True)
        engine.acknowledge_repair(project.name)
        self.assertEqual(project.state, ProjectState.READY)
        self.assertEqual(project.attempts, 0)

    def test_attempt_budget_exhaustion(self) -> None:
        engine = demo_engine()
        project = engine.project("worker-alpha")
        project.attempts = project.max_attempts
        result = engine.schedule()
        self.assertIsNone(result)
        self.assertEqual(project.state, ProjectState.REPAIR_REQUIRED)

    def test_graceful_stop_transaction(self) -> None:
        engine = demo_engine()
        engine.schedule()
        engine.request_stop("worker-alpha")
        self.assertEqual(engine.project("worker-alpha").state, ProjectState.STOPPING)
        engine.confirm_stop("worker-alpha")
        self.assertEqual(engine.project("worker-alpha").state, ProjectState.STOPPED)

    def test_unclean_shutdown_recovery(self) -> None:
        engine = demo_engine()
        engine.schedule()
        engine.schedule()
        held = engine.recover_from_unclean_shutdown()
        self.assertIn("worker-alpha", held)
        self.assertIn("worker-beta", held)
        for name in held:
            engine.reconcile_recovering(name, alive=False)
        self.assertEqual(engine.project("worker-alpha").state, ProjectState.STOPPED)
        self.assertEqual(engine.project("worker-beta").state, ProjectState.STOPPED)

    def test_legal_transition_validation(self) -> None:
        engine = demo_engine()
        engine.schedule()
        with self.assertRaises(ValueError):
            engine._transition(
                engine.project("worker-alpha"),
                ProjectState.READY,
                "illegal jump from RUNNING directly to READY",
            )
        with self.assertRaises(ValueError):
            engine._transition(
                engine.project("worker-alpha"),
                ProjectState.STARTING,
                "illegal jump from RUNNING back to STARTING",
            )


if __name__ == "__main__":
    unittest.main()
