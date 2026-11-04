import ast
from pathlib import Path
import unittest


class PythonConfigTests(unittest.TestCase):
    def test_stub_names_match_runtime_properties(self):
        root = Path(__file__).resolve().parents[1]
        config = root / "sdk/python/pulumi_busbar/config"
        stub = ast.parse((config / "__init__.pyi").read_text())
        declared = {node.target.id for node in stub.body if isinstance(node, ast.AnnAssign)}
        runtime = ast.parse((config / "vars.py").read_text())
        cls = next(node for node in runtime.body if isinstance(node, ast.ClassDef))
        actual = {node.name for node in cls.body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(declared, actual)


if __name__ == "__main__":
    unittest.main()
