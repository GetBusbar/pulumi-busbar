"""Exercise release behavior with local Git remotes and fake compiler/API calls."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        # Fixture repositories must not inherit developer hooks or signing.
        config = patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.excludesFile", "GIT_CONFIG_VALUE_0": os.devnull})
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
        for manifest in ("sdk/python/pulumi_busbar/pulumi-plugin.json", "sdk/go/busbar/pulumi-plugin.json"):
            published = json.loads(self.git("show", f"{remote}:{manifest}"))
            self.assertEqual(published, {"name": "busbar", "server": "github://api.github.com/getbusbar",
                                         "version": "0.2.0"})
        paths = self.git("ls-tree", "-r", "--name-only", remote)
        self.assertNotIn("unrelated", paths)
        self.assertNotIn("index.js", paths)
        self.assertNotIn("package.tgz", paths)
        release.publish_sdk("0.2.0")  # identical retry reuses the existing tag
        self.write("sdk/go.mod", "module github.com/getbusbar/pulumi-busbar/sdk\n\ngo 1.26\n")
        with self.assertRaisesRegex(ValueError, "refusing to replace"):
            release.publish_sdk("0.2.0")
        self.assertEqual(self.git("ls-remote", "origin", "refs/tags/sdk/v0.2.0").split()[0], remote)

    def test_archives_match_downloader_layout_and_checksums(self):
        self.write("LICENSE", "license")
        calls = []

        def compiler(*args, cwd=None, env=None, quiet=False):
            if args[:2] in (("git", "status"), ("git", "ls-files")):
                return ""
            if args[0] == "git":
                return "source"
            calls.append((args, env))
            self.assertIn("-X github.com/getbusbar/pulumi-busbar/provider/pkg/version.Version=0.2.0",
                          args[args.index("-ldflags") + 1])
            self.assertEqual(args[-1], "./cmd/pulumi-resource-busbar")
            self.assertIn("-mod=readonly", args)
            self.assertEqual(env["GOWORK"], "off")
            self.assertEqual(cwd, self.root / "provider")
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
        self.assertEqual({(env["GOOS"], env["GOARCH"]) for _, env in calls}, set(release.TARGETS))
        self.assertEqual(len(release.TARGETS), 6)
        listed = [line.split()[1] for line in (directory / "SHA256SUMS").read_text().splitlines()]
        self.assertEqual(listed, [release.archive_name("0.2.0", *target) for target in release.TARGETS])
        for line in (directory / "SHA256SUMS").read_text().splitlines():
            digest, name = line.split()
            self.assertEqual(digest, hashlib.sha256((directory / name).read_bytes()).hexdigest())
            binary = "pulumi-resource-busbar" + (".exe" if "windows" in name else "")
            with tarfile.open(directory / name) as archive:
                self.assertEqual(archive.getnames(), [binary, "LICENSE"])
                self.assertEqual(archive.getmember(binary).mode, 0o755)
                self.assertEqual(archive.getmember("LICENSE").mode, 0o644)
                for member in archive.getmembers():
                    self.assertEqual((member.uid, member.gid, member.uname, member.gname, member.mtime),
                                     (0, 0, "", "", 0))
            with gzip.open(directory / name) as stream:
                stream.read()
                self.assertEqual(stream.mtime, 0)

    def test_provider_publication_verifies_tag_and_never_clobbers_assets(self):
        directory, names = self.provider_assets()
        calls = []

        def api(*args, **kwargs):
            calls.append(args)
            if args[:2] == ("git", "ls-remote"):
                return "source\trefs/tags/v0.2.0"
            if args[:2] == ("git", "rev-parse"):
                return "source"
            if args[:3] == ("gh", "release", "view"):
                raise subprocess.CalledProcessError(1, args, stderr="release not found\n")
            return ""

        with patch.object(release, "run", side_effect=api):
            release.publish_provider("0.2.0", directory)
        create = next(call for call in calls if call[:3] == ("gh", "release", "create"))
        self.assertIn("--verify-tag", create)
        self.assertEqual(len([c for c in calls if c[:3] == ("gh", "release", "upload")]), 7)
        self.assertTrue(all("--clobber" not in call for call in calls))
        self.assertEqual(calls[-1], ("gh", "release", "edit", "v0.2.0", "--draft=false"))

        def conflicting_api(*args, **kwargs):
            if args[:2] == ("git", "ls-remote"):
                return "source\trefs/tags/v0.2.0"
            if args[:2] == ("git", "rev-parse"):
                return "source"
            if args[:3] == ("gh", "release", "view"):
                return json.dumps({"assets": [{"name": names[0]}], "isDraft": False})
            if args[:3] == ("gh", "release", "download"):
                (Path(args[-1]) / names[0]).write_bytes(b"existing different asset")
                return ""
            self.fail(f"unexpected mutation: {args}")

        with patch.object(release, "run", side_effect=conflicting_api):
            with self.assertRaisesRegex(ValueError, "refusing to replace"):
                release.publish_provider("0.2.0", directory)

    def provider_assets(self):
        directory = self.root / "dist"
        directory.mkdir()
        names = [f"pulumi-resource-busbar-v0.2.0-{system}-{arch}.tar.gz"
                 for system, arch in release.TARGETS] + ["SHA256SUMS"]
        for name in names[:-1]:
            (directory / name).write_bytes(b"fixture " + name.encode())
        (directory / "SHA256SUMS").write_text("".join(
            f"{hashlib.sha256((directory / name).read_bytes()).hexdigest()}  {name}\n"
            for name in names[:-1]))
        return directory, names

    def test_provider_publication_reuses_identical_assets(self):
        directory, names = self.provider_assets()
        calls = []

        def api(*args, **kwargs):
            calls.append(args)
            if args[:2] == ("git", "ls-remote"):
                return "source\trefs/tags/v0.2.0"
            if args[:2] == ("git", "rev-parse"):
                return "source"
            if args[:3] == ("gh", "release", "view"):
                return json.dumps({"assets": [{"name": name} for name in names], "isDraft": False})
            if args[:3] == ("gh", "release", "download"):
                name = args[args.index("--pattern") + 1]
                (Path(args[-1]) / name).write_bytes((directory / name).read_bytes())
                return ""
            self.fail(f"unexpected mutation: {args}")

        with patch.object(release, "run", side_effect=api):
            release.publish_provider("0.2.0", directory)
        self.assertEqual(len([c for c in calls if c[:3] == ("gh", "release", "download")]), 7)

    def test_provider_publication_requires_matching_root_tag(self):
        directory, _ = self.provider_assets()
        for local, remote, head in (("tag", "tag", "other"), ("tag", "moved", "tag")):
            def api(*args, **kwargs):
                if args[:2] == ("git", "ls-remote"):
                    return remote + "\trefs/tags/v0.2.0"
                if args == ("git", "rev-parse", "refs/tags/v0.2.0"):
                    return local
                if args == ("git", "rev-parse", "refs/tags/v0.2.0^{commit}"):
                    return "tag"
                if args == ("git", "rev-parse", "HEAD"):
                    return head
                self.fail(f"unexpected call: {args}")

            with self.subTest(remote=remote, head=head), patch.object(release, "run", side_effect=api):
                with self.assertRaisesRegex(ValueError, "root release tag"):
                    release.publish_provider("0.2.0", directory)

    def test_provider_publication_surfaces_release_lookup_failures(self):
        directory, _ = self.provider_assets()
        calls = []

        def api(*args, **kwargs):
            calls.append(args)
            if args[:2] == ("git", "ls-remote"):
                return "source\trefs/tags/v0.2.0"
            if args[:2] == ("git", "rev-parse"):
                return "source"
            if args[:3] == ("gh", "release", "view"):
                raise subprocess.CalledProcessError(1, args, stderr="HTTP 502: Bad Gateway\n")
            return ""

        with patch.object(release, "run", side_effect=api):
            with self.assertRaises(subprocess.CalledProcessError):
                release.publish_provider("0.2.0", directory)
        self.assertFalse([call for call in calls if call[:2] == ("gh", "release") and call[2] != "view"])

    def test_run_reports_command_errors(self):
        with patch("sys.stderr") as stderr:
            with self.assertRaises(subprocess.CalledProcessError) as raised:
                release.run("git", "rev-parse", "refs/tags/missing", cwd=self.temporary.name)
        self.assertTrue(raised.exception.stderr)
        stderr.write.assert_called_with(raised.exception.stderr)

    def test_archives_require_the_release_tag_checkout(self):
        def api(*args, **kwargs):
            if args[:2] == ("git", "rev-parse"):
                return "tag" if "refs/tags" in args[2] else "other"
            self.fail(f"built from the wrong checkout: {args}")

        with patch.object(release, "run", side_effect=api):
            with self.assertRaisesRegex(ValueError, "root release tag"):
                release.archives("0.2.0", self.root / "dist")

    def test_sdk_publication_refuses_untracked_files(self):
        self.fixture()
        release.prepare("0.2.0")
        self.write("sdk/nodejs/.npmrc", "//registry.npmjs.org/:_authToken=secret\n")
        with self.assertRaisesRegex(ValueError, "sdk/nodejs/.npmrc"):
            release.publish_sdk("0.2.0")
        self.assertEqual(self.git("ls-remote", "origin", "refs/tags/sdk/v0.2.0"), "")

    def test_sdk_publication_refuses_staged_new_files(self):
        self.fixture()
        release.prepare("0.2.0")
        self.write("sdk/python/.env", "BUSBAR_ADMIN_TOKEN=secret\n")
        self.git("add", "-A")
        with self.assertRaisesRegex(ValueError, "sdk/python/.env"):
            release.publish_sdk("0.2.0")
        self.assertEqual(self.git("ls-remote", "origin", "refs/tags/sdk/v0.2.0"), "")

    def test_sdk_publication_refuses_renamed_or_deleted_files(self):
        self.fixture()
        release.prepare("0.2.0")
        self.git("config", "diff.renames", "true")
        for change in ("rename", "delete"):
            with self.subTest(change=change):
                if change == "rename":
                    (self.root / "sdk/go.mod").rename(self.root / "sdk/go.mod.moved")
                else:
                    (self.root / "sdk/go.mod").unlink()
                with self.assertRaisesRegex(ValueError, "sdk/go.mod"):
                    release.publish_sdk("0.2.0")
                (self.root / "sdk/go.mod.moved").unlink(missing_ok=True)
                self.git("checkout", "-q", "--", "sdk/go.mod")
        self.assertEqual(self.git("ls-remote", "origin", "refs/tags/sdk/v0.2.0"), "")

    def test_missing_tool_is_a_refusal(self):
        with patch.dict(os.environ, {"PATH": self.temporary.name}):
            with self.assertRaisesRegex(release.ReleaseError, "gh is not installed"):
                release.run("gh", "release", "view", "v0.2.0")

    def test_archives_name_hidden_changes_and_allow_vendored_modules(self):
        self.write("provider/resources.go", "package busbar\n")
        self.write("LICENSE", "license")
        self.fixture()
        real_run = release.run
        builds = []

        def compiler(*args, cwd=None, env=None, quiet=False):
            if args[0] == "git":
                return real_run(*args, cwd=cwd, env=env, quiet=quiet)
            builds.append(args)
            Path(args[args.index("-o") + 1]).write_bytes(b"binary")
            return ""

        (self.root / ".git/info/exclude").write_text("provider/vendor/\nprovider/zz_local.go\n")
        self.write("provider/vendor/example.com/mod/mod.go", "package mod\n")
        with patch.object(release, "run", side_effect=compiler):
            release.archives("0.2.0", self.root / "dist")
            self.assertEqual(len(builds), 6)
            self.write("provider/zz_local.go", "package busbar\n")
            with self.assertRaisesRegex(ValueError, "provider/zz_local.go"):
                release.archives("0.2.0", self.root / "dist")

    def test_provider_publication_refuses_unexpected_assets(self):
        directory, names = self.provider_assets()

        def api(*args, **kwargs):
            if args[:2] == ("git", "ls-remote"):
                return "source\trefs/tags/v0.2.0"
            if args[:2] == ("git", "rev-parse"):
                return "source"
            if args[:3] == ("gh", "release", "view"):
                return json.dumps({"assets": [{"name": "debug.tar.gz"}], "isDraft": True})
            self.fail(f"published a release with unexpected assets: {args}")

        with patch.object(release, "run", side_effect=api):
            with self.assertRaisesRegex(ValueError, "debug.tar.gz"):
                release.publish_provider("0.2.0", directory)

    def test_command_line_keeps_context_for_unexpected_errors(self):
        script = self.root / "scripts/release.py"
        script.parent.mkdir()
        script.write_text(Path(release.__file__).read_text())
        self.fixture()
        self.write("sdk/python/pulumi_busbar/pulumi-plugin.json", "{")
        result = subprocess.run([sys.executable, str(script), "prepare", "0.2.0"], cwd=self.root,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Traceback", result.stderr)
        self.assertIn("JSONDecodeError", result.stderr)

    def test_sdk_publication_requires_the_go_version_stamp(self):
        self.fixture()
        release.prepare("0.2.0")
        self.write("sdk/go/busbar/internal/pulumiVersion.go",
                   "var SdkVersion semver.Version = semver.Version{}\n")
        with self.assertRaisesRegex(ValueError, "prepare"):
            release.publish_sdk("0.2.0")
        self.assertEqual(self.git("ls-remote", "origin", "refs/tags/sdk/v0.2.0"), "")

    def test_sdk_publication_requires_the_published_root_tag(self):
        self.fixture()
        release.prepare("0.2.0")
        self.git("push", "-q", "origin", ":refs/tags/v0.2.0")
        with self.assertRaisesRegex(ValueError, "missing remote root tag"):
            release.publish_sdk("0.2.0")
        self.assertEqual(self.git("ls-remote", "origin", "refs/tags/sdk/v0.2.0"), "")

    def test_sdk_publication_requires_every_prepared_version(self):
        self.fixture()
        release.prepare("0.2.0")
        for relative in ("sdk/nodejs/package.json", "sdk/python/pulumi_busbar/pulumi-plugin.json",
                         "sdk/go/busbar/pulumi-plugin.json"):
            with self.subTest(file=relative):
                path = self.root / relative
                stamped = path.read_text()
                path.write_text(json.dumps({**json.loads(stamped), "version": "0.1.0"}))
                with self.assertRaisesRegex(ValueError, "prepare"):
                    release.publish_sdk("0.2.0")
                path.write_text(stamped)
        self.assertEqual(self.git("ls-remote", "origin", "refs/tags/sdk/v0.2.0"), "")

    def test_missing_tag_error_keeps_git_detail(self):
        self.fixture()
        with self.assertRaisesRegex(ValueError, "missing root release tag v0.4.0: (?!git exited).+"):
            release.prepare("0.4.0")

    def test_sdk_publication_requires_prepared_versions(self):
        self.fixture()
        with self.assertRaisesRegex(ValueError, "prepare"):
            release.publish_sdk("0.2.0")
        self.assertEqual(self.git("ls-remote", "origin", "refs/tags/sdk/v0.2.0"), "")

    def stamped_files(self):
        return {name: (self.root / name).read_text() for name in (
            "sdk/nodejs/package.json", "sdk/python/pulumi_busbar/pulumi-plugin.json",
            "sdk/go/busbar/pulumi-plugin.json", "sdk/go/busbar/internal/pulumiVersion.go")}

    def test_prepare_validates_before_writing(self):
        self.fixture()
        self.git("tag", "v0.3.0")
        before = self.stamped_files()
        with self.assertRaisesRegex(ValueError, "Python SDK"):
            release.prepare("0.3.0")
        self.assertEqual(self.stamped_files(), before)
        self.write("sdk/python/setup.py", 'VERSION = "0.3.0"\n')
        self.write("sdk/go/busbar/pulumi-plugin.json", "{")
        with self.assertRaises(ValueError):
            release.prepare("0.3.0")
        self.assertEqual(self.stamped_files(), {**before, "sdk/go/busbar/pulumi-plugin.json": "{"})
        self.write("sdk/go/busbar/pulumi-plugin.json", before["sdk/go/busbar/pulumi-plugin.json"])
        self.write("sdk/go/busbar/internal/pulumiVersion.go", "package internal\n")
        with self.assertRaisesRegex(ValueError, "Go SDK"):
            release.prepare("0.3.0")
        self.assertEqual(self.stamped_files(),
                         {**before, "sdk/go/busbar/internal/pulumiVersion.go": "package internal\n"})

    def test_prepare_requires_the_release_tag_checkout(self):
        self.fixture()
        self.git("commit", "--allow-empty", "-qm", "after release")
        before = self.stamped_files()
        with self.assertRaisesRegex(ValueError, "root release tag"):
            release.prepare("0.2.0")
        with self.assertRaisesRegex(ValueError, "root release tag"):
            release.prepare("0.4.0")
        self.assertEqual(self.stamped_files(), before)

    def test_archives_reject_uncommitted_provider_sources(self):
        self.write("provider/resources.go", "package busbar\n")
        self.write("LICENSE", "license")
        self.fixture()
        real_run = release.run
        builds = []

        def compiler(*args, cwd=None, env=None, quiet=False):
            if args[0] == "git":
                return real_run(*args, cwd=cwd, env=env, quiet=quiet)
            builds.append(args)
            Path(args[args.index("-o") + 1]).write_bytes(b"binary")
            return ""

        self.write("provider/cmd/pulumi-resource-busbar/schema-embed.json", '{"regenerated": true}')
        with patch.object(release, "run", side_effect=compiler):
            release.archives("0.2.0", self.root / "dist")
            self.assertEqual(len(builds), 6)
            for edit in ("provider/resources.go", "provider/extra.go", "LICENSE",
                         "provider/cmd/pulumi-resource-busbar/bridge-metadata.json"):
                with self.subTest(edit=edit):
                    self.write(edit, "changed")
                    with self.assertRaisesRegex(ValueError, "differ from the root tag"):
                        release.archives("0.2.0", self.root / "dist")
                    self.git("checkout", "-q", "--", ".")
                    self.git("clean", "-qfd", "provider")
        self.assertEqual(len(builds), 6)

    def test_failed_archives_rerun_removes_stale_checksums(self):
        directory = self.root / "dist"
        directory.mkdir()
        (directory / "SHA256SUMS").write_text("stale\n")
        self.write("LICENSE", "license")
        calls = []

        def compiler(*args, cwd=None, env=None, quiet=False):
            if args[:2] in (("git", "status"), ("git", "ls-files")):
                return ""
            if args[0] == "git":
                return "source"
            calls.append(args)
            if len(calls) == 3:
                raise subprocess.CalledProcessError(1, args)
            Path(args[args.index("-o") + 1]).write_bytes(b"binary")
            return ""

        with patch.object(release, "run", side_effect=compiler):
            with self.assertRaises(subprocess.CalledProcessError):
                release.archives("0.2.0", directory)
        self.assertFalse((directory / "SHA256SUMS").exists())

    def test_provider_publication_finalises_an_existing_draft(self):
        directory, names = self.provider_assets()
        calls = []

        def api(*args, **kwargs):
            calls.append(args)
            if args[:2] == ("git", "ls-remote"):
                return "source\trefs/tags/v0.2.0"
            if args[:2] == ("git", "rev-parse"):
                return "source"
            if args[:3] == ("gh", "release", "view"):
                return json.dumps({"assets": [{"name": names[0]}], "isDraft": True})
            if args[:3] == ("gh", "release", "download"):
                (Path(args[-1]) / names[0]).write_bytes((directory / names[0]).read_bytes())
            return ""

        with patch.object(release, "run", side_effect=api):
            release.publish_provider("0.2.0", directory)
        self.assertEqual(len([c for c in calls if c[:3] == ("gh", "release", "upload")]), 6)
        self.assertEqual(calls[-1], ("gh", "release", "edit", "v0.2.0", "--draft=false"))

    def test_archives_reject_hidden_provider_changes(self):
        self.write("provider/resources.go", "package busbar\n")
        self.write("LICENSE", "license")
        self.fixture()
        real_run = release.run

        def compiler(*args, cwd=None, env=None, quiet=False):
            if args[0] == "git":
                return real_run(*args, cwd=cwd, env=env, quiet=quiet)
            self.fail(f"built hidden changes: {args}")

        with patch.object(release, "run", side_effect=compiler):
            for flag in ("--assume-unchanged", "--skip-worktree"):
                with self.subTest(flag=flag):
                    self.git("update-index", flag, "provider/resources.go")
                    self.write("provider/resources.go", "package busbar\n// local\n")
                    with self.assertRaisesRegex(ValueError, "differ from the root tag"):
                        release.archives("0.2.0", self.root / "dist")
                    self.git("update-index", flag.replace("--", "--no-"), "provider/resources.go")
                    self.git("checkout", "-q", "--", "provider/resources.go")
            (self.root / ".git/info/exclude").write_text("provider/zz_local.go\n")
            self.write("provider/zz_local.go", "package busbar\n")
            with self.assertRaisesRegex(ValueError, "differ from the root tag"):
                release.archives("0.2.0", self.root / "dist")

    def test_command_line_reports_refusals_without_traceback(self):
        # A copy of the script resolves ROOT to the fixture, never to this checkout.
        script = self.root / "scripts/release.py"
        script.parent.mkdir()
        script.write_text(Path(release.__file__).read_text())
        for arguments, message in ((["prepare", "v1.2.3"], "stable v0/v1 version"),
                                   (["prepare", "1.2.3"], "missing root release tag v1.2.3")):
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, str(script), *arguments], cwd=self.root,
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_provider_publication_rejects_unverified_archives(self):
        directory, names = self.provider_assets()

        def api(*args, **kwargs):
            if args[:2] == ("git", "ls-remote"):
                return "source\trefs/tags/v0.2.0"
            if args[:2] == ("git", "rev-parse"):
                return "source"
            self.fail(f"published unverified assets: {args}")

        for corrupt in ("archive", "listing"):
            with self.subTest(corrupt=corrupt), patch.object(release, "run", side_effect=api):
                sums = (directory / "SHA256SUMS").read_text()
                if corrupt == "archive":
                    (directory / names[0]).write_bytes(b"truncated")
                else:
                    (directory / "SHA256SUMS").write_text(sums.split("\n", 1)[1])
                with self.assertRaisesRegex(ValueError, "SHA256SUMS"):
                    release.publish_provider("0.2.0", directory)
                (directory / "SHA256SUMS").write_text(sums)
                (directory / names[0]).write_bytes(b"fixture " + names[0].encode())

    def test_rejects_unsupported_versions_and_stale_python_sdk(self):
        for version in ("2.0.0", "01.0.0", "0.2.0-rc.1", "0.2.0; echo bad"):
            with self.assertRaises(ValueError):
                release.validate_version(version)
        self.fixture()
        self.git("tag", "v0.3.0")
        with self.assertRaisesRegex(ValueError, "Python SDK"):
            release.prepare("0.3.0")


if __name__ == "__main__":
    unittest.main()
