import json
from pathlib import Path
import unittest


class NodePackageTests(unittest.TestCase):
    def test_package_points_at_compiler_output_and_copies_version_metadata(self):
        root = Path(__file__).resolve().parents[1]
        package = json.loads((root / "sdk/nodejs/package.json").read_text())
        self.assertEqual(package.get("main"), "bin/index.js")
        self.assertEqual(package.get("types"), "bin/index.d.ts")
        self.assertIn("bin/package.json", package["scripts"]["build"])
        self.assertEqual(package["scripts"].get("prepack"), "npm run build")


if __name__ == "__main__":
    unittest.main()
