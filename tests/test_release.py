"""Exercise release behavior with local Git remotes and fake compiler/API calls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        # Fixture repositories must not inherit developer hooks or signing.
        config = patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
        config.start()
        self.addCleanup(config.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.patch = patch.object(release, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    def git(self, *args):
        return release.run("git", *args)

    def fixture(self):
        self.write("sdk/go.mod", "module github.com/getbusbar/pulumi-busbar/sdk\n")
        self.write("sdk/nodejs/package.json", '{"name":"@getbusbar/pulumi-busbar","version":"${VERSION}"}')
        self.write("sdk/python/setup.py", 'VERSION = "0.2.0"\n')
        for path in ("sdk/python/pulumi_busbar/pulumi-plugin.json", "sdk/go/busbar/pulumi-plugin.json"):
            self.write(path, '{"name":"busbar","server":"github://api.github.com/getbusbar"}')
        self.write("sdk/go/busbar/internal/pulumiVersion.go",
                   "var SdkVersion semver.Version = semver.Version{}\n")
        self.write("provider/cmd/pulumi-resource-busbar/schema-embed.json", '{}')
        self.write(".gitignore", "sdk/nodejs/bin/\nsdk/nodejs/*.tgz\n")
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.test")
        self.git("add", ".")
        self.git("commit", "-qm", "Release source")
        self.git("tag", "v0.2.0")
        remote = Path(self.temporary.name) / "remote.git"
        release.run("git", "init", "--bare", "-q", str(remote))
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "origin", "refs/tags/v0.2.0")

    def test_sdk_tag_commits_versioned_sources_and_never_moves_existing_tag(self):
        self.fixture()
        source = self.git("rev-parse", "HEAD")
        release.prepare("0.2.0")
        self.write("sdk/nodejs/bin/index.js", "build output")
        self.write("sdk/nodejs/package.tgz", "packed output")
        self.write("unrelated", "do not publish")
        self.git("add", "unrelated")
        release.publish_sdk("0.2.0")
        remote = self.git("ls-remote", "origin", "refs/tags/sdk/v0.2.0").split()[0]
        self.assertNotEqual(remote, source)
        self.assertEqual(self.git("rev-parse", "refs/tags/v0.2.0"), source)
        self.assertEqual(self.git("rev-parse", remote + "^"), source)
        package = json.loads(self.git("show", remote + ":sdk/nodejs/package.json"))
        self.assertEqual(package["version"], "0.2.0")
        self.assertIn('semver.MustParse("0.2.0")', self.git("show", remote + ":sdk/go/busbar/internal/pulumiVersion.go"))
        paths = self.git("ls-tree", "-r", "--name-only", remote)
        self.assertNotIn("unrelated", paths)
        self.assertNotIn("index.js", paths)
        self.assertNotIn("package.tgz", paths)
        release.publish_sdk("0.2.0")  # identical retry reuses the existing tag
        self.write("sdk/changed.go", "different generation")
        with self.assertRaisesRegex(ValueError, "refusing to replace"):
            release.publish_sdk("0.2.0")
        self.assertEqual(self.git("ls-remote", "origin", "refs/tags/sdk/v0.2.0").split()[0], remote)

    def test_archives_match_downloader_layout_and_checksums(self):
        self.write("LICENSE", "license")
        calls = []

        def compiler(*args, cwd=None, env=None):
            calls.append((args, env))
            self.assertIn("Version=0.2.0", args[args.index("-ldflags") + 1])
            self.assertEqual(env["CGO_ENABLED"], "0")
            binary = Path(args[args.index("-o") + 1])
            binary.write_bytes((env["GOOS"] + "/" + env["GOARCH"]).encode())

        directory = self.root / "dist"
        with patch.object(release, "run", side_effect=compiler):
            release.archives("0.2.0", directory)
            first = {path.name: path.read_bytes() for path in directory.iterdir()}
            release.archives("0.2.0", directory)
        self.assertEqual(first, {path.name: path.read_bytes() for path in directory.iterdir()})
        self.assertEqual(len(calls), 12)
        for line in (directory / "SHA256SUMS").read_text().splitlines():
            digest, name = line.split()
            self.assertEqual(digest, hashlib.sha256((directory / name).read_bytes()).hexdigest())
            binary = "pulumi-resource-busbar" + (".exe" if "windows" in name else "")
            with tarfile.open(directory / name) as archive:
                self.assertEqual(archive.getnames(), [binary, "LICENSE"])
                self.assertEqual(archive.getmember(binary).mode, 0o755)

    def test_provider_publication_verifies_tag_and_never_clobbers_assets(self):
        directory = self.root / "dist"
        directory.mkdir()
        names = [f"pulumi-resource-busbar-v0.2.0-{system}-{arch}.tar.gz"
                 for system, arch in release.TARGETS] + ["SHA256SUMS"]
        for name in names:
            (directory / name).write_bytes(b"fixture")
        calls = []

        def api(*args, **kwargs):
            calls.append(args)
            if args[:2] == ("git", "ls-remote"):
                return "source\trefs/tags/v0.2.0"
            if args[:3] == ("gh", "release", "view"):
                raise subprocess.CalledProcessError(1, args)
            return ""

        with patch.object(release, "run", side_effect=api):
            release.publish_provider("0.2.0", directory)
        create = next(call for call in calls if call[:3] == ("gh", "release", "create"))
        self.assertIn("--verify-tag", create)
        self.assertEqual(len([c for c in calls if c[:3] == ("gh", "release", "upload")]), 7)
        self.assertTrue(all("--clobber" not in call for call in calls))

        def conflicting_api(*args, **kwargs):
            if args[:2] == ("git", "ls-remote"):
                return "source\trefs/tags/v0.2.0"
            if args[:3] == ("gh", "release", "view"):
                return json.dumps({"assets": [{"name": names[0]}], "isDraft": False})
            if args[:3] == ("gh", "release", "download"):
                (Path(args[-1]) / names[0]).write_bytes(b"existing different asset")
                return ""
            self.fail(f"unexpected mutation: {args}")

        with patch.object(release, "run", side_effect=conflicting_api):
            with self.assertRaisesRegex(ValueError, "refusing to replace"):
                release.publish_provider("0.2.0", directory)

    def test_rejects_unsupported_versions_and_stale_python_sdk(self):
        for version in ("2.0.0", "01.0.0", "0.2.0-rc.1", "0.2.0; echo bad"):
            with self.assertRaises(ValueError):
                release.validate_version(version)
        self.fixture()
        with self.assertRaisesRegex(ValueError, "Python SDK"):
            release.prepare("0.3.0")


if __name__ == "__main__":
    unittest.main()
