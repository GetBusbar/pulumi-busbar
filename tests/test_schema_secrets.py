"""Regression checks for secrets in the published Pulumi schema."""
import json
from pathlib import Path
import unittest


class SchemaSecretsTests(unittest.TestCase):
    def test_config_document_is_secret_for_create_read_and_lookup(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "provider/cmd/pulumi-resource-busbar/schema-embed.json").read_text())
        config = schema["resources"]["busbar:index/config:Config"]
        for properties in (config["inputProperties"], config["properties"],
                           config["stateInputs"]["properties"]):
            with self.subTest(properties=properties):
                self.assertTrue(properties["document"].get("secret", False),
                                "Config documents contain plaintext provider credentials")


if __name__ == "__main__":
    unittest.main()
