import ast
import builtins
from pathlib import Path
import types
from typing import Optional
import unittest


class Secret:
    def __init__(self, value):
        self.value = value

    @classmethod
    def __class_getitem__(cls, _):
        return cls

    @staticmethod
    def secret(value):
        return Secret(value)


class SecretConfigTests(unittest.TestCase):
    def test_python_credentials_and_environment_remain_secret(self):
        root = Path(__file__).resolve().parents[1]
        source = ast.parse((root / "sdk/python/pulumi_busbar/config/vars.py").read_text())
        cls = next(n for n in source.body if isinstance(n, ast.ClassDef))
        config = types.SimpleNamespace(
            get=lambda key: "credential", get_secret=lambda key: Secret("credential"))
        globals_ = {"_builtins": builtins, "types": types, "Optional": Optional,
                    "pulumi": types.SimpleNamespace(Output=Secret), "__config__": config,
                    "_utilities": types.SimpleNamespace(get_env=lambda *args: "environment")}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), "config/vars.py", "exec"), globals_)
        module = globals_["_ExportableConfig"]("config")
        self.assertIsInstance(module.client_key_pem, Secret)
        self.assertIsInstance(module.token, Secret)
        config.get_secret = lambda key: None
        self.assertEqual(module.token.value, "environment")
        globals_["_utilities"].get_env = lambda *args: None
        self.assertIsNone(module.token)

    def test_node_and_go_accessors_use_secret_apis(self):
        root = Path(__file__).resolve().parents[1]
        node = (root / "sdk/nodejs/config/vars.ts").read_text()
        go = (root / "sdk/go/busbar/config/config.go").read_text()
        self.assertIn('__config.getSecret("token")', node)
        self.assertIn('__config.getSecret("clientKeyPem")', node)
        self.assertIn("pulumi.secret(env)", node)
        self.assertIn('config.TrySecret(ctx, "busbar:token")', go)
        self.assertIn('config.GetSecret(ctx, "busbar:clientKeyPem")', go)
        self.assertIn("pulumi.ToSecret(value)", go)


if __name__ == "__main__":
    unittest.main()
