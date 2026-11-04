"""Build provider assets and publish the generated Go SDK without moving tags."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [(system, arch) for system in ("linux", "darwin", "windows")
           for arch in ("amd64", "arm64")]


def run(*args, cwd=None, env=None):
    return subprocess.check_output(args, cwd=cwd or ROOT, env=env, text=True).strip()


def validate_version(version):
    # The checked-in module has no /vN suffix. A major release needs a module
    # migration first; never publish an unusable sdk/v2 tag for this module.
    if not re.fullmatch(r"[01]\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise ValueError("release requires a stable v0/v1 version matching sdk/go.mod")
    return version


def prepare(version):
    validate_version(version)
    package_path = ROOT / "sdk/nodejs/package.json"
    package = json.loads(package_path.read_text())
    package["version"] = version
    package_path.write_text(json.dumps(package, indent=4) + "\n")
    # Python's generator already respects the schema version. Reject stale
    # generation rather than silently publish a different package version.
    setup = (ROOT / "sdk/python/setup.py").read_text()
    if f'VERSION = "{version}"' not in setup:
        raise ValueError("Python SDK was not generated with the release version")
    for relative in ("sdk/python/pulumi_busbar/pulumi-plugin.json",
                     "sdk/go/busbar/pulumi-plugin.json"):
        path = ROOT / relative
        manifest = json.loads(path.read_text())
        manifest["version"] = version
        path.write_text(json.dumps(manifest, indent=2) + "\n")
    path = ROOT / "sdk/go/busbar/internal/pulumiVersion.go"
    source, count = re.subn(r"var SdkVersion semver.Version = [^\n]+",
                           f'var SdkVersion semver.Version = semver.MustParse("{version}")',
                           path.read_text())
    if count != 1:
        raise ValueError("unrecognized generated Go SDK version declaration")
    path.write_text(source)


def archives(version, destination):
    validate_version(version)
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    checksums = []
    with tempfile.TemporaryDirectory(prefix="busbar-release-") as directory:
        for system, arch in TARGETS:
            name = "pulumi-resource-busbar" + (".exe" if system == "windows" else "")
            binary = Path(directory) / name
            env = dict(os.environ, GOOS=system, GOARCH=arch, CGO_ENABLED="0")
            run("go", "build", "-trimpath", "-buildvcs=false", "-o", str(binary), "-ldflags",
                "-s -w -X github.com/getbusbar/pulumi-busbar/provider/pkg/version.Version=" + version,
                "./cmd/pulumi-resource-busbar", cwd=ROOT / "provider", env=env)
            archive = destination / f"pulumi-resource-busbar-v{version}-{system}-{arch}.tar.gz"
            with archive.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped:
                with tarfile.open(fileobj=zipped, mode="w") as output:
                    for path, member_name in ((binary, name), (ROOT / "LICENSE", "LICENSE")):
                        info = output.gettarinfo(path, arcname=member_name)
                        info.uid = info.gid = info.mtime = 0
                        info.uname = info.gname = ""
                        info.mode = 0o644 if member_name == "LICENSE" else 0o755
                        with path.open("rb") as contents:
                            output.addfile(info, contents)
            checksums.append(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
    (destination / "SHA256SUMS").write_text("".join(checksums))


def publish_sdk(version):
    validate_version(version)
    source = run("git", "rev-parse", f"refs/tags/v{version}^{{commit}}")
    if source != run("git", "rev-parse", "HEAD"):
        raise ValueError("SDK publication must start at the immutable root release tag")
    # An isolated index includes only generated SDKs/schema, never build output
    # or unrelated staged changes. A deterministic commit makes retries safe.
    with tempfile.TemporaryDirectory(prefix="busbar-sdk-index-") as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"))
        run("git", "read-tree", source, env=env)
        run("git", "add", "sdk", "provider/cmd/pulumi-resource-busbar/schema-embed.json", env=env)
        tree = run("git", "write-tree", env=env)
    date = run("git", "show", "-s", "--format=%cI", source)
    env = dict(os.environ, GIT_AUTHOR_NAME="github-actions[bot]",
               GIT_AUTHOR_EMAIL="41898282+github-actions[bot]@users.noreply.github.com",
               GIT_COMMITTER_NAME="github-actions[bot]",
               GIT_COMMITTER_EMAIL="41898282+github-actions[bot]@users.noreply.github.com",
               GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    commit = run("git", "commit-tree", tree, "-p", source,
                 "-m", f"Release generated SDK v{version}", env=env)
    tag = f"refs/tags/sdk/v{version}"
    existing = run("git", "ls-remote", "origin", tag)
    if existing:
        run("git", "fetch", "--no-tags", "origin", tag)
        if run("git", "rev-parse", "FETCH_HEAD^{commit}") != commit:
            raise ValueError(f"refusing to replace existing sdk/v{version}")
    else:
        # A simultaneous publisher can only make this fail; no force update.
        run("git", "push", "origin", f"{commit}:{tag}")
    print(f"sdk/v{version}: {commit}")


def publish_provider(version, destination):
    validate_version(version)
    destination = Path(destination).resolve()
    names = [f"pulumi-resource-busbar-v{version}-{system}-{arch}.tar.gz"
             for system, arch in TARGETS] + ["SHA256SUMS"]
    for name in names:
        if not (destination / name).is_file():
            raise ValueError(f"missing release asset: {name}")
    tag = "v" + version
    # Verify the remote root tag; gh must never implicitly create one.
    if not run("git", "ls-remote", "origin", f"refs/tags/{tag}"):
        raise ValueError(f"missing remote root tag {tag}")
    try:
        release = json.loads(run("gh", "release", "view", tag, "--json", "assets,isDraft"))
    except subprocess.CalledProcessError:
        run("gh", "release", "create", tag, "--verify-tag", "--draft",
            "--title", tag, "--notes", f"Busbar Pulumi provider and SDKs {tag}.")
        release = {"assets": [], "isDraft": True}
    existing = {asset["name"] for asset in release["assets"]}
    # Never clobber assets on a retry. Byte differences require investigation.
    with tempfile.TemporaryDirectory(prefix="busbar-release-assets-") as directory:
        for name in names:
            if name in existing:
                run("gh", "release", "download", tag, "--pattern", name, "--dir", directory)
                if (Path(directory) / name).read_bytes() != (destination / name).read_bytes():
                    raise ValueError(f"refusing to replace existing release asset {name}")
            else:
                run("gh", "release", "upload", tag, str(destination / name))
    if release["isDraft"]:
        run("gh", "release", "edit", tag, "--draft=false")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["validate", "prepare", "archives", "publish-sdk", "publish-provider"])
    parser.add_argument("version", type=validate_version)
    parser.add_argument("--destination", default="dist/provider")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.version)
    elif args.action == "archives":
        archives(args.version, args.destination)
    elif args.action == "publish-sdk":
        publish_sdk(args.version)
    elif args.action == "publish-provider":
        publish_provider(args.version, args.destination)


if __name__ == "__main__":
    main()
