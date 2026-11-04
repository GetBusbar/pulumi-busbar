import json
from pathlib import Path
import unittest


class OptionalCredentialTests(unittest.TestCase):
    def test_creation_only_credentials_can_be_absent(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "provider/cmd/pulumi-resource-busbar/schema-embed.json").read_text())
        required = schema["resources"]["busbar:index/virtualKey:VirtualKey"]["required"]
        for name in ("awsAccessKeyId", "awsSecretAccessKey", "secret"):
            self.assertNotIn(name, required)


if __name__ == "__main__":
    unittest.main()
