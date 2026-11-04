"""Keep the external SDK generator aligned with the provider's Pulumi pin."""
from pathlib import Path
import re
import subprocess
import sys


def required_version():
    module = (Path(__file__).resolve().parents[1] / "provider/go.mod").read_text()
    return re.search(r"github\.com/pulumi/pulumi/pkg/v3\s+(v\S+)", module).group(1)


def check_version():
    expected = required_version()
    try:
        actual = subprocess.check_output(["pulumi", "version"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        actual = "unavailable"
    if actual != expected:
        print(f"SDK generation requires Pulumi CLI {expected} (provider/go.mod); "
              f"found {actual}. Install that version and put it on PATH.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--required-version"]:
        print(required_version().removeprefix("v"))
    else:
        sys.exit(check_version())
