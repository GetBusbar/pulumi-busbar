"""Exercise only the drift recipe; provider generation runs in CI."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class DriftTests(unittest.TestCase):
    def test_untracked_generated_source_fails_drift(self):
        makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text()
        block = makefile.split("drift::", 1)[1].split("\n\n", 1)[0]
        commands = [line.lstrip("\t@").replace("$$", "$")
                    for line in block.splitlines()[1:] if line.startswith("\t")]
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(["git", "init", "-q", directory], check=True)
            result = subprocess.run(["sh", "-ec", "\n".join(commands)], cwd=directory, capture_output=True)
            self.assertEqual(result.returncode, 0)
            Path(directory, "newResource.ts").write_text("export const resource = 1;\n")
            result = subprocess.run(["sh", "-ec", "\n".join(commands)], cwd=directory, capture_output=True)
            self.assertNotEqual(result.returncode, 0, "new generated source must fail drift")


if __name__ == "__main__":
    unittest.main()
