"""Post-processing must fail loudly when generated code no longer matches its anchors."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts import prepare_go, prepare_nodejs, prepare_python

ROOT = Path(__file__).resolve().parents[1]


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

    def copy(self, relative):
        destination = Path(self.temporary.name) / relative
        shutil.copytree(ROOT / relative, destination,
                        ignore=shutil.ignore_patterns("node_modules", "bin", "__pycache__"))
        return destination

    def snapshot(self, directory):
        return {path: path.read_bytes() for path in directory.rglob("*") if path.is_file()}

    def test_committed_sdks_are_already_prepared(self):
        for relative, module in (("sdk/go", prepare_go), ("sdk/nodejs", prepare_nodejs),
                                 ("sdk/python", prepare_python)):
            with self.subTest(sdk=relative):
                directory = self.copy(relative)
                before = self.snapshot(directory)
                module.prepare(directory)
                self.assertEqual(before, self.snapshot(directory))

    def regenerate(self, relative, stock):
        """Return the committed SDK with selected edits undone to the generator's stock text."""
        directory = self.copy(relative)
        for path, edits in stock.items():
            source = (directory / path).read_text()
            for prepared, generated in edits:
                self.assertIn(prepared, source)
                source = source.replace(prepared, generated)
            (directory / path).write_text(source)
        return directory

    def test_rewrites_apply_to_generator_output(self):
        go = {
            "busbar/config/config.go": [
                ("func GetClientKeyPem(ctx *pulumi.Context) pulumi.StringOutput {",
                 "func GetClientKeyPem(ctx *pulumi.Context) string {"),
                ('config.GetSecret(ctx, "busbar:clientKeyPem")', 'config.Get(ctx, "busbar:clientKeyPem")'),
                ("func GetToken(ctx *pulumi.Context) pulumi.StringOutput {",
                 "func GetToken(ctx *pulumi.Context) string {"),
                ('config.TrySecret(ctx, "busbar:token")', 'config.Try(ctx, "busbar:token")'),
                ("return pulumi.ToSecret(value).(pulumi.StringOutput)", "return value")],
        }
        copy_args = ("\tif args != nil {\n\t\targsCopy := *args\n\t\targs = &argsCopy\n\t}\n", "")
        copy_opts = ("opts = append(append([]pulumi.ResourceOption(nil), opts...), secrets)",
                     "opts = append(opts, secrets)")
        go["busbar/provider.go"] = [copy_args, copy_opts]
        for name, filename in (("Config", "config.go"), ("Hook", "hook.go"), ("VirtualKey", "virtualKey.go")):
            go[f"busbar/{filename}"] = [copy_opts] + ([copy_args] if name != "VirtualKey" else []) + [
                (f"{name}Array{{resource}} // resource is returned by New{name}.", f"{name}Array{{ {name}Args{{...}} }}"),
                (f'{name}Map{{"key": resource}} // resource is returned by New{name}.',
                 f'{name}Map{{ "key": {name}Args{{...}} }}')]
        nodejs = {
            "config/vars.ts": [
                ("export declare const clientKeyPem: pulumi.Output<string> | undefined;",
                 "export declare const clientKeyPem: string | undefined;"),
                ('__config.getSecret("clientKeyPem")', '__config.get("clientKeyPem")'),
                ("export declare const token: pulumi.Output<string> | undefined;",
                 "export declare const token: string | undefined;"),
                ('const value = __config.getSecret("token");\n'
                 '        if (value !== undefined) { return value; }\n'
                 '        const env = utilities.getEnv("BUSBAR_ADMIN_TOKEN");\n'
                 '        return env === undefined ? undefined : pulumi.secret(env);',
                 'return __config.get("token") ?? utilities.getEnv("BUSBAR_ADMIN_TOKEN");')],
            "provider.ts": [
                ('const token = args?.token || utilities.getEnv("BUSBAR_ADMIN_TOKEN");\n'
                 '            resourceInputs["token"] = token ? pulumi.secret(token) : undefined;',
                 'resourceInputs["token"] = (args?.token ? pulumi.secret(args.token) : undefined)'
                 ' ?? utilities.getEnv("BUSBAR_ADMIN_TOKEN");')],
        }
        python = {
            "pulumi_busbar/config/__init__.pyi": [
                ("client_key_pem: Optional[pulumi.Output[str]]", "clientKeyPem: Optional[str]"),
                ("token: Optional[pulumi.Output[str]]", "token: Optional[str]")],
            "pulumi_busbar/config/vars.py": [
                ("def client_key_pem(self) -> Optional[pulumi.Output[str]]:",
                 "def client_key_pem(self) -> Optional[str]:"),
                ("__config__.get_secret('clientKeyPem')", "__config__.get('clientKeyPem')"),
                ("def token(self) -> Optional[pulumi.Output[str]]:", "def token(self) -> Optional[str]:"),
                ("value = __config__.get_secret('token')\n"
                 "        if value is not None:\n"
                 "            return value\n"
                 "        value = _utilities.get_env('BUSBAR_ADMIN_TOKEN')\n"
                 "        return pulumi.Output.secret(value) if value is not None else None",
                 "return __config__.get('token') or _utilities.get_env('BUSBAR_ADMIN_TOKEN')")],
        }
        for relative, module, stock in (("sdk/go", prepare_go, go), ("sdk/nodejs", prepare_nodejs, nodejs),
                                        ("sdk/python", prepare_python, python)):
            with self.subTest(sdk=relative):
                directory = self.regenerate(relative, stock)
                module.prepare(directory)
                for path in stock:
                    self.assertEqual((directory / path).read_text(), (ROOT / relative / path).read_text())

    def test_go_secret_accessor_change_fails(self):
        directory = self.copy("sdk/go")
        path = directory / "busbar/config/config.go"
        path.write_text(path.read_text().replace(
            'config.GetSecret(ctx, "busbar:clientKeyPem")', 'config.Require(ctx, "busbar:clientKeyPem")'))
        with self.assertRaisesRegex(ValueError, "clientKeyPem"):
            prepare_go.prepare(directory)

    def test_go_token_rewrite_stays_inside_get_token(self):
        directory = self.copy("sdk/go")
        path = directory / "busbar/config/config.go"
        later = ("\nfunc GetUser(ctx *pulumi.Context) string {\n\tvar value string\n"
                 "\treturn value\n}\n")
        path.write_text(path.read_text() + later)
        prepare_go.prepare(directory)
        self.assertTrue(path.read_text().endswith(later))

    def test_nodejs_secret_accessor_change_fails(self):
        directory = self.copy("sdk/nodejs")
        path = directory / "config/vars.ts"
        path.write_text(path.read_text().replace('__config.getSecret("clientKeyPem")',
                                                 '__config.require("clientKeyPem")'))
        with self.assertRaisesRegex(ValueError, "clientKeyPem"):
            prepare_nodejs.prepare(directory)

    def test_python_secret_accessor_change_fails(self):
        directory = self.copy("sdk/python")
        path = directory / "pulumi_busbar/config/vars.py"
        path.write_text(path.read_text().replace("__config__.get_secret('clientKeyPem')",
                                                 "__config__.require('clientKeyPem')"))
        with self.assertRaisesRegex(ValueError, "clientKeyPem"):
            prepare_python.prepare(directory)

    def test_python_missing_config_class_fails_clearly(self):
        directory = self.copy("sdk/python")
        path = directory / "pulumi_busbar/config/vars.py"
        path.write_text(path.read_text().replace("class _ExportableConfig", "class _RenamedConfig"))
        with self.assertRaisesRegex(ValueError, "_ExportableConfig"):
            prepare_python.prepare(directory)


@unittest.skipUnless(shutil.which("node"), "node is required to evaluate the generated constructor")
class NodeProviderTokenTests(unittest.TestCase):
    def token_input(self, args, environment):
        source = (ROOT / "sdk/nodejs/provider.ts").read_text()
        lines = [line for line in source.splitlines()
                 if 'resourceInputs["token"]' in line or "const token =" in line]
        self.assertTrue(lines)
        program = (
            "const pulumi = { secret: value => ({ secret: value }) };\n"
            f"const utilities = {{ getEnv: () => {json.dumps(environment)} ?? undefined }};\n"
            f"const args = {json.dumps(args)};\n"
            "const resourceInputs = {};\n{\n" + "\n".join(lines) + "\n}\n"
            "process.stdout.write(JSON.stringify(resourceInputs.token ?? null));\n")
        result = subprocess.run(["node", "-e", program], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_environment_token_is_secret(self):
        self.assertEqual(self.token_input({}, "environment"), {"secret": "environment"})
        self.assertEqual(self.token_input({"token": "argument"}, "environment"), {"secret": "argument"})
        self.assertIsNone(self.token_input({}, None))


if __name__ == "__main__":
    unittest.main()
