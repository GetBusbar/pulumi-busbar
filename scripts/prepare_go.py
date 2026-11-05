"""Preserve secrets and caller-owned inputs in generated Go SDKs."""
from pathlib import Path
import sys


def prepare(directory):
    path = Path(directory) / "busbar/config/config.go"
    source = path.read_text(encoding="utf-8")
    source = source.replace("func GetClientKeyPem(ctx *pulumi.Context) string {",
                            "func GetClientKeyPem(ctx *pulumi.Context) pulumi.StringOutput {")
    source = source.replace('config.Get(ctx, "busbar:clientKeyPem")',
                            'config.GetSecret(ctx, "busbar:clientKeyPem")')
    source = source.replace("func GetToken(ctx *pulumi.Context) string {",
                            "func GetToken(ctx *pulumi.Context) pulumi.StringOutput {")
    source = source.replace('config.Try(ctx, "busbar:token")',
                            'config.TrySecret(ctx, "busbar:token")')
    start = source.index("func GetToken(")
    source = source[:start] + source[start:].replace(
        "return value", "return pulumi.ToSecret(value).(pulumi.StringOutput)")
    path.write_text(source, encoding="utf-8")
    for name, filename in (("Provider", "provider.go"), ("Config", "config.go"),
                           ("Hook", "hook.go")):
        path = Path(directory) / "busbar" / filename
        source = path.read_text(encoding="utf-8")
        anchor = (f"name string, args *{name}Args, opts ...pulumi.ResourceOption) "
                  f"(*{name}, error) {{\n\tif args == nil {{")
        replacement = (f"name string, args *{name}Args, opts ...pulumi.ResourceOption) "
                       f"(*{name}, error) {{\n\tif args != nil {{\n"
                       "\t\targsCopy := *args\n\t\targs = &argsCopy\n\t}\n\tif args == nil {")
        source = source.replace(anchor, replacement)
        path.write_text(source, encoding="utf-8")
    for filename in ("provider.go", "config.go", "hook.go", "virtualKey.go"):
        path = Path(directory) / "busbar" / filename
        source = path.read_text(encoding="utf-8").replace(
            "opts = append(opts, secrets)",
            "opts = append(append([]pulumi.ResourceOption(nil), opts...), secrets)")
        path.write_text(source, encoding="utf-8")

    for name, filename in (("Config", "config.go"), ("Hook", "hook.go"),
                           ("VirtualKey", "virtualKey.go")):
        path = Path(directory) / "busbar" / filename
        source = path.read_text(encoding="utf-8")
        source = source.replace(
            name + "Array{ " + name + "Args{...} }",
            name + "Array{resource} // resource is returned by New" + name + ".")
        source = source.replace(
            name + 'Map{ "key": ' + name + 'Args{...} }',
            name + 'Map{"key": resource} // resource is returned by New' + name + ".")
        path.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    prepare(sys.argv[1])
