from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supervisor_public import (  # noqa: E402
    PauseCause,
    Project,
    ProjectState,
    RunMode,
    demo_engine,
)


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


class RunModeTests(unittest.TestCase):
    """The supervisor run mode (network_ready x automation_paused) is one
    declared state with validated transitions, not two loose booleans."""

    def test_operator_pause_blocks_scheduling(self) -> None:
        engine = demo_engine()
        engine.pause_automation()
        self.assertEqual(engine.run_mode, RunMode.OPERATOR_HOLD)
        self.assertTrue(engine.automation_paused)
        self.assertIsNone(engine.schedule())

    def test_operator_pause_parks_running_projects(self) -> None:
        engine = demo_engine()
        project = engine.schedule()
        engine.pause_automation()
        self.assertEqual(project.state, ProjectState.PAUSED)
        self.assertEqual(project.paused_by, {PauseCause.OPERATOR})

    def test_resume_automation_releases_projects(self) -> None:
        engine = demo_engine()
        project = engine.schedule()
        engine.pause_automation()
        engine.resume_automation()
        self.assertEqual(engine.run_mode, RunMode.NORMAL)
        self.assertEqual(project.state, ProjectState.READY)
        self.assertIsNotNone(engine.schedule())

    def test_recover_network_honors_operator_hold(self) -> None:
        # Regression: a network flap-and-recovery must not release a
        # project the operator parked.
        engine = demo_engine()
        project = engine.schedule()
        engine.pause_automation()
        engine.disconnect()
        self.assertEqual(engine.run_mode, RunMode.DUAL_HOLD)
        engine.recover_network()
        self.assertEqual(engine.run_mode, RunMode.OPERATOR_HOLD)
        self.assertTrue(engine.automation_paused)
        self.assertEqual(project.state, ProjectState.PAUSED)
        self.assertIsNone(engine.schedule())

    def test_operator_hold_stacks_over_network_pause(self) -> None:
        engine = demo_engine()
        project = engine.schedule()
        engine.disconnect()
        engine.pause_automation()
        self.assertEqual(engine.run_mode, RunMode.DUAL_HOLD)
        self.assertEqual(project.paused_by, {PauseCause.NETWORK, PauseCause.OPERATOR})
        engine.recover_network()
        self.assertEqual(project.state, ProjectState.PAUSED)
        self.assertIsNone(engine.schedule())
        engine.resume_automation()
        self.assertEqual(project.state, ProjectState.READY)
        self.assertIsNotNone(engine.schedule())

    def test_network_hold_stacks_over_operator_pause(self) -> None:
        engine = demo_engine()
        project = engine.schedule()
        engine.pause_automation()
        engine.disconnect()
        self.assertEqual(project.paused_by, {PauseCause.OPERATOR, PauseCause.NETWORK})
        engine.resume_automation()
        self.assertEqual(engine.run_mode, RunMode.NETWORK_HOLD)
        self.assertEqual(project.state, ProjectState.PAUSED)
        engine.recover_network()
        self.assertEqual(project.state, ProjectState.READY)

    def test_run_mode_rejects_illegal_transitions(self) -> None:
        engine = demo_engine()
        with self.assertRaises(ValueError):
            engine.recover_network()
        with self.assertRaises(ValueError):
            engine.resume_automation()
        engine.disconnect()
        with self.assertRaises(ValueError):
            engine.disconnect()
        with self.assertRaises(ValueError):
            engine.resume_automation()
        engine.recover_network()
        engine.pause_automation()
        with self.assertRaises(ValueError):
            engine.pause_automation()

    def test_run_mode_flags_are_derived_and_read_only(self) -> None:
        engine = demo_engine()
        self.assertTrue(engine.network_ready)
        self.assertFalse(engine.automation_paused)
        with self.assertRaises(AttributeError):
            engine.automation_paused = True
        with self.assertRaises(AttributeError):
            engine.network_ready = False
        engine.disconnect()
        self.assertFalse(engine.network_ready)
        self.assertFalse(engine.automation_paused)

    def test_unknown_run_mode_fails_loudly(self) -> None:
        engine = demo_engine()
        engine.run_mode = "bogus"
        with self.assertRaises(ValueError):
            engine.schedule()

    def test_paused_requires_recorded_cause(self) -> None:
        engine = demo_engine()
        project = engine.schedule()
        with self.assertRaises(ValueError):
            engine._transition(project, ProjectState.PAUSED, "no cause recorded")
        with self.assertRaises(ValueError):
            Project("p", priority=1, weight=1, state=ProjectState.PAUSED)


if __name__ == "__main__":
    unittest.main()
