"""Reject incompatible external generators before they can rewrite the SDKs."""
import contextlib
import io
import subprocess
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
