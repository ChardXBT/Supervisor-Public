from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_generator():
    path = ROOT / "scripts" / "generate_demo_asset.py"
    spec = importlib.util.spec_from_file_location("asset_generator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AssetPrivacyTests(unittest.TestCase):
    def test_sanitizer_masks_common_identity_shapes(self) -> None:
        module = load_generator()
        home = "C:" + "\\Users\\" + "example\\project"
        email = "person" + "@" + "example.test"
        credential = "token" + "=" + "sample-value"
        long_id = "01234567" * 3
        source = f"{home} {email} {credential} {long_id}"
        sanitized = module.sanitize(source)
        self.assertNotIn(email, sanitized)
        self.assertNotIn("sample-value", sanitized)
        self.assertNotIn(long_id, sanitized)
        self.assertIn("[redacted]", sanitized)


if __name__ == "__main__":
    unittest.main()
