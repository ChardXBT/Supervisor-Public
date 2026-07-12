from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from self_recovering_automation.monitor import WIDTH, render_monitor  # noqa: E402


class MonitorTests(unittest.TestCase):
    def test_screen_is_stable_and_monitor_only(self) -> None:
        screen = render_monitor()
        self.assertIn("MONITOR ONLY", screen)
        self.assertIn("no external processes or services", screen)
        self.assertIn("writes and launches are blocked", screen)
        self.assertTrue(all(len(line) == WIDTH for line in screen.splitlines()))

    def test_screen_contains_no_identity_shaped_content(self) -> None:
        screen = render_monitor()
        self.assertNotIn("@", screen)
        self.assertNotIn("\\Users\\", screen)
        self.assertNotIn("http", screen.casefold())


if __name__ == "__main__":
    unittest.main()
