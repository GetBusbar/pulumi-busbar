"""Align generated config stubs and preserve secret config outputs."""
import ast
from pathlib import Path
import re
import sys


def prepare(directory):
    config = Path(directory) / "pulumi_busbar/config"
    runtime = ast.parse((config / "vars.py").read_text(encoding="utf-8"))
    stub_path = config / "__init__.pyi"
    stub = stub_path.read_text(encoding="utf-8")
    cls = next(node for node in runtime.body
               if isinstance(node, ast.ClassDef) and node.name == "_ExportableConfig")
    for function in cls.body:
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "__config__" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                stub = re.sub(r"(?m)^" + re.escape(node.args[0].value) + ":",
                              function.name + ":", stub)
    for name in ("token", "client_key_pem"):
        stub = stub.replace(f"{name}: Optional[str]", f"{name}: Optional[pulumi.Output[str]]")
    stub_path.write_text(stub, encoding="utf-8")
    runtime_path = config / "vars.py"
    source = runtime_path.read_text(encoding="utf-8")
    for name in ("token", "client_key_pem"):
        source = source.replace(f"def {name}(self) -> Optional[str]:",
                                f"def {name}(self) -> Optional[pulumi.Output[str]]:")
    source = source.replace("__config__.get('clientKeyPem')", "__config__.get_secret('clientKeyPem')")
    source = source.replace(
        "return __config__.get('token') or _utilities.get_env('BUSBAR_ADMIN_TOKEN')",
        "value = __config__.get_secret('token')\n"
        "        if value is not None:\n"
        "            return value\n"
        "        value = _utilities.get_env('BUSBAR_ADMIN_TOKEN')\n"
        "        return pulumi.Output.secret(value) if value is not None else None")
    runtime_path.write_text(source, encoding="utf-8")
    readme = Path(directory) / "pulumi_busbar/README.md"
    (Path(directory) / "README.md").write_text(readme.read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    prepare(sys.argv[1])
