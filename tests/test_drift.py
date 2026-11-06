"""Exercise only the drift recipe; provider generation needs the pinned Pulumi CLI."""
import os
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
        # Fixture repositories must not inherit developer ignores, hooks or templates.
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.excludesFile",
                   GIT_CONFIG_VALUE_0=os.devnull,
                   GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.test",
                   GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.test")

        def drift(directory):
            return subprocess.run(["sh", "-ec", "\n".join(commands)], cwd=directory,
                                  capture_output=True, env=env).returncode

        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(["git", "init", "-q", directory], check=True, env=env)
            self.assertEqual(drift(directory), 0)
            Path(directory, "newResource.ts").write_text("export const resource = 1;\n")
            self.assertNotEqual(drift(directory), 0, "new generated source must fail drift")
            subprocess.run(["git", "add", "newResource.ts"], cwd=directory, check=True, env=env)
            subprocess.run(["git", "commit", "-qm", "generated"], cwd=directory, check=True, env=env)
            self.assertEqual(drift(directory), 0)
            Path(directory, "newResource.ts").write_text("export const resource = 2;\n")
            self.assertNotEqual(drift(directory), 0, "changed generated source must fail drift")


if __name__ == "__main__":
    unittest.main()
