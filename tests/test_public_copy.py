from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicCopyTests(unittest.TestCase):
    def test_readme_has_architecture_section_and_plain_wording(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Architecture", readme)
        self.assertIn("```", readme)
        self.assertNotIn("control plane", readme.lower())
        self.assertNotIn("reference implementation", readme.lower())

    def test_architecture_doc_exists(self) -> None:
        arch = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
        self.assertIn("Supervisor", arch)
        self.assertIn("```", arch)


if __name__ == "__main__":
    unittest.main()
