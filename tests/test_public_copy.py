from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicCopyTests(unittest.TestCase):
    def test_readme_has_manager_flow_and_plain_wording(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Manager flow", readme)
        self.assertGreaterEqual(readme.count("```mermaid"), 2)
        self.assertNotIn("control plane", readme.lower())
        self.assertNotIn("orchestration", readme.lower())
        self.assertNotIn("reference implementation", readme.lower())
        self.assertNotIn("—", readme)
        self.assertNotIn("–", readme)


if __name__ == "__main__":
    unittest.main()
