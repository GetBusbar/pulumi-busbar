"""Prepare generated package layout and secret config accessors."""
import json
from pathlib import Path
import sys


def rewrite(source, old, new):
    """Apply one post-processing edit, or fail if the generated code changed shape."""
    if old in source:
        return source.replace(old, new)
    if new in source:
        return source
    raise ValueError(f"generated Node.js SDK no longer contains {old!r}")


def prepare(directory):
    path = Path(directory) / "package.json"
    package = json.loads(path.read_text(encoding="utf-8"))
    package["main"] = "bin/index.js"
    package["types"] = "bin/index.d.ts"
    package["files"] = ["bin", "README.md"]
    # Clear old compiler output so modules removed from the SDK are not packed.
    package.setdefault("scripts", {})["build"] = (
        'node -e "require(\'fs\').rmSync(\'bin\', {recursive: true, force: true})" && '
        'tsc && node -e "require(\'fs\').copyFileSync(\'package.json\', \'bin/package.json\')"'
    )
    package["scripts"]["prepack"] = "npm run build"
    package["scripts"]["test"] = "npm run build && node --test tests/virtualKey.test.js"
    path.write_text(json.dumps(package, indent=4) + "\n", encoding="utf-8")
    config_path = Path(directory) / "config/vars.ts"
    config = config_path.read_text(encoding="utf-8")
    for name in ("token", "clientKeyPem"):
        config = rewrite(config, f"export declare const {name}: string | undefined;",
                         f"export declare const {name}: pulumi.Output<string> | undefined;")
    config = rewrite(config, '__config.get("clientKeyPem")', '__config.getSecret("clientKeyPem")')
    config = rewrite(
        config,
        'return __config.get("token") ?? utilities.getEnv("BUSBAR_ADMIN_TOKEN");',
        'const value = __config.getSecret("token");\n'
        '        if (value !== undefined) { return value; }\n'
        '        const env = utilities.getEnv("BUSBAR_ADMIN_TOKEN");\n'
        '        return env === undefined ? undefined : pulumi.secret(env);')
    config_path.write_text(config, encoding="utf-8")
    # The explicit provider must keep its environment token secret, like the Go
    # and Python constructors do.
    provider_path = Path(directory) / "provider.ts"
    provider = rewrite(
        provider_path.read_text(encoding="utf-8"),
        'resourceInputs["token"] = (args?.token ? pulumi.secret(args.token) : undefined)'
        ' ?? utilities.getEnv("BUSBAR_ADMIN_TOKEN");',
        'const token = args?.token || utilities.getEnv("BUSBAR_ADMIN_TOKEN");\n'
        '            resourceInputs["token"] = token ? pulumi.secret(token) : undefined;')
    provider_path.write_text(provider, encoding="utf-8")


if __name__ == "__main__":
    prepare(sys.argv[1])
