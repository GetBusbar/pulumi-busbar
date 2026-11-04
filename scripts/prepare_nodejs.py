"""Prepare generated package layout and secret config accessors."""
import json
from pathlib import Path
import sys


def prepare(directory):
    path = Path(directory) / "package.json"
    package = json.loads(path.read_text(encoding="utf-8"))
    package["main"] = "bin/index.js"
    package["types"] = "bin/index.d.ts"
    package["files"] = ["bin", "README.md"]
    package.setdefault("scripts", {})["build"] = (
        'tsc && node -e "require(\'fs\').copyFileSync(\'package.json\', \'bin/package.json\')"'
    )
    package["scripts"]["prepack"] = "npm run build"
    package["scripts"]["test"] = "npm run build && node --test tests/virtualKey.test.js"
    path.write_text(json.dumps(package, indent=4) + "\n", encoding="utf-8")
    config_path = Path(directory) / "config/vars.ts"
    config = config_path.read_text(encoding="utf-8")
    for name in ("token", "clientKeyPem"):
        config = config.replace(f"export declare const {name}: string | undefined;",
                                f"export declare const {name}: pulumi.Output<string> | undefined;")
    config = config.replace('__config.get("clientKeyPem")', '__config.getSecret("clientKeyPem")')
    config = config.replace(
        'return __config.get("token") ?? utilities.getEnv("BUSBAR_ADMIN_TOKEN");',
        'const value = __config.getSecret("token");\n'
        '        if (value !== undefined) { return value; }\n'
        '        const env = utilities.getEnv("BUSBAR_ADMIN_TOKEN");\n'
        '        return env === undefined ? undefined : pulumi.secret(env);')
    config_path.write_text(config, encoding="utf-8")


if __name__ == "__main__":
    prepare(sys.argv[1])
