"""Regressions for documentation emitted from the bridge's upstream sources."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class GeneratedDocumentationTests(unittest.TestCase):
    def test_examples_and_literal_identifiers_survive_generation(self):
        files = [ROOT / "provider/cmd/pulumi-resource-busbar/schema-embed.json"]
        for extension in ("*.go", "*.ts", "*.py"):
            # Generated sources only: skip installed packages and compiler output.
            files.extend(path for path in (ROOT / "sdk").rglob(extension)
                         if not {"node_modules", "bin"} & set(path.relative_to(ROOT).parts))
        for path in files:
            text = path.read_text(encoding="utf-8")
            for invalid in ("busbarAdminToken", "busbar_admin_token", "%!v(PANIC=", "BUSBAR*CONFIG*OVERLAY", "issue*aws*credential", "GetInfo(ctx, map[string]interface{}"):
                self.assertNotIn(invalid, text, str(path))
        schema = json.loads(files[0].read_text())
        description = schema["functions"]["busbar:index/getInfo:getInfo"]["description"]
        self.assertIn("busbar.GetInfo(ctx)", description)
        self.assertIn("pulumi.String(current.Version)", description)
        self.assertIn("pulumi.ToStringArray(current.AuthModules)", description)

if __name__ == "__main__":
    unittest.main()
