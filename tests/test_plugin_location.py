import json
from pathlib import Path
import unittest


class PluginLocationTests(unittest.TestCase):
    def test_generated_packages_use_the_getbusbar_plugin_server(self):
        root = Path(__file__).resolve().parents[1]
        server = "github://api.github.com/getbusbar"
        schema = json.loads((root / "provider/cmd/pulumi-resource-busbar/schema-embed.json").read_text())
        self.assertEqual(schema.get("pluginDownloadURL"), server)
        for manifest in ("sdk/go/busbar/pulumi-plugin.json",
                         "sdk/python/pulumi_busbar/pulumi-plugin.json"):
            self.assertEqual(json.loads((root / manifest).read_text()).get("server"), server)
        package = json.loads((root / "sdk/nodejs/package.json").read_text())
        self.assertEqual(package["pulumi"].get("server"), server)


if __name__ == "__main__":
    unittest.main()
