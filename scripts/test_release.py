"""Exercise publication channels and failure gates without invoking GitHub or Git."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from validation import ValidationError

SPEC = importlib.util.spec_from_file_location("release", Path(__file__).with_name("release.py"))
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
SHA = "a" * 40


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.calls = []
        self.existing_tag = False
        self.ci_runs = [{"name": "CI", "head_sha": SHA, "conclusion": "success"}]

    def fixture(self, version):
        (self.root / "Cargo.toml").write_text(f'[package]\nversion = "{version}"\n', encoding="utf-8")
        (self.root / "CHANGELOG.md").write_text(f"# Changelog\n\n## {version}\n\nUseful change.\n\n## 0.0.1\n\nOld.\n", encoding="utf-8")
        dist = self.root / "dist"
        dist.mkdir()
        for target in ("x86_64-pc-windows-msvc", "x86_64-unknown-linux-musl"):
            archive = dist / f"ods2tsv-{version}-{target}.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("README.txt", "Synthetic publication fixture; not an executable.")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")

    def check_output(self, command, **kwargs):
        if command == ["git", "rev-parse", "HEAD"]:
            return SHA + "\n"
        if command[:3] == ["git", "ls-remote", "--tags"]:
            return f"{SHA}\t{command[-1]}\n" if self.existing_tag else ""
        if command[:2] == ["gh", "api"]:
            self.assertIn(f"head_sha={SHA}&event=push", command[2])
            return json.dumps({"workflow_runs": self.ci_runs})
        raise AssertionError(f"Unexpected external command: {command}")

    def publish(self, command, **kwargs):
        self.assertEqual(command[:3], ["gh", "release", "create"])
        self.assertTrue(kwargs["check"])
        self.assertEqual(kwargs["cwd"], self.root)
        self.calls.append(command)

    def invoke(self, publish=True, ref="refs/heads/main", environment_sha=SHA):
        environment = {"GITHUB_REF": ref, "GITHUB_SHA": environment_sha,
                       "GITHUB_OUTPUT": str(self.root / "outputs.txt")}
        fake_tools = SimpleNamespace(check_output=self.check_output, run=self.publish)
        with patch.object(release, "ROOT", self.root), patch.object(release, "subprocess", fake_tools), \
             patch.dict(release.os.environ, environment, clear=True), \
             patch("sys.argv", ["release.py", *(["--publish"] if publish else [])]), \
             contextlib.redirect_stdout(io.StringIO()):
            release.main()

    def test_stable_uses_normal_release_channel_and_versioned_notes(self):
        self.fixture("0.1.0")
        self.invoke()
        command, = self.calls
        self.assertEqual(command[3], "0.1.0")
        self.assertNotIn("--prerelease", command)
        self.assertNotIn("--latest=false", command)
        self.assertNotIn("--latest", command)
        self.assertNotIn("--latest=true", command)
        self.assertEqual(command[command.index("--target") + 1], SHA)
        self.assertEqual(len([part for part in command if part.endswith((".zip", ".sha256"))]), 4)
        notes = (self.root / "dist/release-notes.md").read_text(encoding="utf-8")
        self.assertIn("This is a stable release.", notes)
        self.assertNotIn("experimental prerelease", notes)
        self.assertNotIn("Old.", notes)
        self.assertIn("/blob/0.1.0/README.md", notes)
        self.assertEqual((self.root / "outputs.txt").read_text(encoding="utf-8"), "version=0.1.0\n")

    def test_all_supported_prerelease_channels_stay_prereleases(self):
        for stage in ("alpha", "beta", "rc"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                self.root = Path(temporary)
                self.calls = []
                self.fixture(f"0.1.0-{stage}.1")
                self.invoke()
                command, = self.calls
                self.assertIn("--prerelease", command)
                self.assertIn("--latest=false", command)
                self.assertIn("experimental prerelease", (self.root / "dist/release-notes.md").read_text(encoding="utf-8"))

    def test_dry_run_does_not_publish_or_prepare_notes(self):
        self.fixture("0.1.0")
        self.invoke(publish=False)
        self.assertFalse(self.calls)
        self.assertFalse((self.root / "dist/release-notes.md").exists())

    def test_unsupported_or_noncanonical_versions_cannot_publish(self):
        self.fixture("0.1.0-rc.1")
        for version in ("v0.1.0", "0.1", "0.1.0-dev.1", "01.0.0", "0.1.0-rc.01", "0.1.0+build"):
            (self.root / "Cargo.toml").write_text(f'[package]\nversion = "{version}"\n', encoding="utf-8")
            with self.subTest(version=version), self.assertRaisesRegex(ValidationError, "Unsupported release version"):
                self.invoke()
            self.assertFalse(self.calls)

    def test_wrong_branch_or_commit_cannot_publish(self):
        self.fixture("0.1.0-rc.1")
        for arguments, diagnostic in (({"ref": "refs/heads/topic"}, "Release must run from main"),
                                      ({"environment_sha": "b" * 40}, "commit differs from GITHUB_SHA")):
            with self.subTest(arguments=arguments), self.assertRaisesRegex(ValidationError, diagnostic):
                self.invoke(**arguments)
            self.assertFalse(self.calls)

    def test_only_successful_ci_for_the_exact_commit_allows_publication(self):
        self.fixture("0.1.0-rc.1")
        for runs in ([], [{"name": "CI", "head_sha": "b" * 40, "conclusion": "success"}],
                     [{"name": "CI", "head_sha": SHA, "conclusion": "failure"}],
                     [{"name": "Other", "head_sha": SHA, "conclusion": "success"}]):
            self.ci_runs = runs
            with self.subTest(runs=runs), self.assertRaisesRegex(ValidationError, "Exact main commit"):
                self.invoke()
            self.assertFalse(self.calls)

    def test_existing_tag_cannot_be_replaced(self):
        self.fixture("0.1.0-rc.1")
        self.existing_tag = True
        with self.assertRaisesRegex(ValidationError, "Tag already exists"):
            self.invoke()
        self.assertFalse(self.calls)

    def test_missing_or_unexpected_archive_cannot_publish(self):
        self.fixture("0.1.0-rc.1")
        first, *_ = (self.root / "dist").glob("*.zip")
        original = first.read_bytes()
        first.unlink()
        with self.subTest(case="missing"), self.assertRaisesRegex(ValidationError, "Missing or unexpected"):
            self.invoke()
        self.assertFalse(self.calls)
        first.write_bytes(original)
        first.with_name("unexpected.zip").write_bytes(original)
        with self.subTest(case="unexpected"), self.assertRaisesRegex(ValidationError, "Missing or unexpected"):
            self.invoke()
        self.assertFalse(self.calls)

    def test_wrong_checksum_or_sidecar_filename_cannot_publish(self):
        self.fixture("0.1.0-rc.1")
        first, *_ = (self.root / "dist").glob("*.sha256")
        original = first.read_text(encoding="utf-8")
        for content in ("0" * 64 + original[64:], original.replace("ods2tsv-", "other-")):
            first.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaisesRegex(ValidationError, "checksum or sidecar filename differs"):
                self.invoke()
            self.assertFalse(self.calls)

    def test_missing_release_notes_cannot_publish(self):
        self.fixture("0.1.0-rc.1")
        (self.root / "CHANGELOG.md").write_text("# No entry\n", encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "No changelog entry"):
            self.invoke()
        self.assertFalse(self.calls)


if __name__ == "__main__":
    unittest.main()
