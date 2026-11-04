import json
from pathlib import Path
import unittest


class PythonVersionTests(unittest.TestCase):
    def test_python_generator_uses_release_version(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "provider/cmd/pulumi-resource-busbar/schema-embed.json").read_text())
        self.assertTrue(schema["language"]["python"].get("respectSchemaVersion", False))


if __name__ == "__main__":
    unittest.main()
