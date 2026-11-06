import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class NodePackageTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.package = json.loads((root / "sdk/nodejs/package.json").read_text())

    def test_package_points_at_compiler_output_and_copies_version_metadata(self):
        package = self.package
        self.assertEqual(package.get("main"), "bin/index.js")
        self.assertEqual(package.get("types"), "bin/index.d.ts")
        self.assertIn("bin/package.json", package["scripts"]["build"])
        self.assertEqual(package["scripts"].get("prepack"), "npm run build")

    @unittest.skipUnless(shutil.which("node"), "node is required to run the build steps")
    def test_build_removes_stale_compiler_output_before_compiling(self):
        steps = self.package["scripts"]["build"].split(" && ")
        self.assertIn("tsc", steps)
        before_compile = steps[:steps.index("tsc")]
        with tempfile.TemporaryDirectory() as directory:
            stale = Path(directory, "bin", "removedResource.js")
            stale.parent.mkdir()
            stale.write_text("module.exports = {};\n")
            for step in before_compile:
                subprocess.run(step, shell=True, cwd=directory, check=True)
            self.assertFalse(stale.exists(), "packed SDK would ship modules removed from the schema")


if __name__ == "__main__":
    unittest.main()
