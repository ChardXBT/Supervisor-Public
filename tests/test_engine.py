from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from self_recovering_automation import JobState, demo_engine  # noqa: E402


class AutomationEngineTests(unittest.TestCase):
    def test_priority_and_capacity_prevent_start_storm(self) -> None:
        engine = demo_engine()
        first = engine.schedule()
        second = engine.schedule()
        self.assertEqual(first.name, "live-monitor")
        self.assertEqual(second.name, "daily-report")
        self.assertIsNone(engine.schedule())
        self.assertLessEqual(engine.running_weight, engine.capacity)

    def test_disconnect_pauses_without_marking_complete(self) -> None:
        engine = demo_engine()
        job = engine.schedule()
        engine.disconnect()
        self.assertEqual(job.state, JobState.PAUSED)
        self.assertNotEqual(job.state, JobState.COMPLETE)

    def test_recovery_requires_explicit_release(self) -> None:
        engine = demo_engine()
        job = engine.schedule()
        engine.fail(job.name, retryable=True)
        self.assertEqual(job.state, JobState.COOLDOWN)
        engine.release_cooldown(job.name)
        self.assertEqual(job.state, JobState.READY)

    def test_permanent_failure_is_not_retried(self) -> None:
        engine = demo_engine()
        job = engine.schedule()
        engine.fail(job.name, retryable=False)
        self.assertEqual(job.state, JobState.ATTENTION)
        self.assertNotEqual(engine.schedule(), job)


if __name__ == "__main__":
    unittest.main()
