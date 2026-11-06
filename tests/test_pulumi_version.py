"""Reject incompatible external generators before they can rewrite the SDKs."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import check_pulumi
from scripts.check_pulumi import check_version, required_version


class PulumiVersionTests(unittest.TestCase):
    def test_generator_version(self):
        expected = required_version()
        with patch("scripts.check_pulumi.subprocess.check_output", return_value=expected + "\n"):
            self.assertEqual(check_version(), 0)
        for result in ["v0.0.0", FileNotFoundError(), subprocess.CalledProcessError(1, "pulumi")]:
            with self.subTest(result=result), contextlib.redirect_stderr(io.StringIO()) as stderr:
                kwargs = {"side_effect": result} if isinstance(result, Exception) else {"return_value": result}
                with patch("scripts.check_pulumi.subprocess.check_output", **kwargs):
                    self.assertEqual(check_version(), 1)
                self.assertIn(expected, stderr.getvalue())

    def test_missing_pulumi_pin_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / "go.mod"
            module.write_text("module example.test\n\nrequire github.com/pulumi/pulumi/sdk/v3 v3.1.0\n")
            with patch.object(check_pulumi, "GO_MOD", module):
                with self.assertRaisesRegex(ValueError, "github.com/pulumi/pulumi/pkg/v3"):
                    required_version()

    def test_command_line(self):
        script = Path(check_pulumi.__file__)
        printed = subprocess.run([sys.executable, str(script), "--required-version"],
                                 capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(printed, required_version().removeprefix("v"))


if __name__ == "__main__":
    unittest.main()
