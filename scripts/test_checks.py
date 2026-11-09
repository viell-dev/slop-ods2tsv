"""Network-free controls for package, documentation, dependency and license gates."""
import contextlib
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import artifact
import check
import dependencies
import licenses
from markdown_links import check_links, heading_anchors
import package
from release_metadata import portable_guide

ROOT = Path(__file__).resolve().parent.parent


class MarkdownTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "README.md").write_text("# Start\n")
        (self.root / "docs").mkdir()
        (self.root / "docs/guide.md").write_text('# Café: `value`\n## Repeat\n## Repeat\n<a id="custom"></a>\n')
        (self.root / "research/nested").mkdir(parents=True)

    def test_existing_inline_reference_and_explicit_anchors(self):
        (self.root / "README.md").write_text(
            "# Start\n[Same](#start) [Other](docs/guide.md#caf%C3%A9-value)\n"
            "[Repeated][guide]\n[guide]: docs/guide.md#repeat-1\n"
            "[Custom](docs/guide.md#custom)\n```md\n[Ignored](absent.md)\n```\n")
        check_links(self.root)

    def test_each_missing_file_or_section_reports_source_and_target(self):
        for target in ("absent.md", "docs/guide.md#absent", "#absent"):
            with self.subTest(target=target):
                (self.root / "README.md").write_text(f"# Start\n[Broken]({target})\n")
                with self.assertRaisesRegex(ValueError, "README.md") as error:
                    check_links(self.root)
                self.assertIn(target, str(error.exception))

    def test_nested_research_is_checked_but_generated_results_are_excluded(self):
        nested = self.root / "research/nested/README.md"
        nested.write_text("[Broken](absent.md)\n")
        with self.assertRaisesRegex(ValueError, "nested.*README.md.*absent.md"):
            check_links(self.root)
        nested.write_text("# Research\n")
        (self.root / "research/results").mkdir()
        (self.root / "research/results/generated.md").write_text("[Ignored](absent.md)")
        check_links(self.root)

    def test_duplicate_and_setext_heading_ids(self):
        self.assertEqual(heading_anchors("A *heading*\n===\n## A heading\n## A heading-1\n## A heading\n"),
                         {"a-heading", "a-heading-1", "a-heading-1-1", "a-heading-2"})


class PackageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.version = "0.1.1"
        self.target = "x86_64-pc-windows-msvc" if sys.platform == "win32" else "x86_64-unknown-linux-musl"
        for relative in ("docs/PORTABLE.txt", "LICENSE", "licenses/README.md", "licenses/musl-1.2.5.COPYRIGHT"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / relative).read_bytes())
        for name, text in (("COPYRIGHT-library.html", "Copyright notices for The Rust Standard Library"),
                           ("licenses/MIT.txt", "Synthetic MIT fixture"),
                           ("licenses/Apache-2.0.txt", "Synthetic Apache fixture")):
            path = self.root / "licenses/rust" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def build_fixture(self):
        (self.root / "Cargo.toml").write_text(f'[package]\nversion = "{self.version}"\n')
        binary_name = "ods2tsv.exe" if self.target.endswith("msvc") else "ods2tsv"
        binary = self.root / "target" / self.target / "release" / binary_name
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(b"Synthetic binary; never execute this fixture.")
        runtime = [(str(path.relative_to(self.root)).replace("\\", "/"), path)
                   for path in (self.root / "licenses").rglob("*")
                   if path.is_file() and not (self.target.endswith("msvc") and path.name.startswith("musl-"))]
        with patch.object(package, "ROOT", self.root), \
             patch.object(package, "notices", return_value="Third-party notices for this target: synthetic"), \
             patch.object(package, "runtime_files", return_value=runtime), \
             patch.object(package.subprocess, "run"), \
             patch.object(package.subprocess, "check_output", return_value=f"ods2tsv {self.version}\n"), \
             patch("sys.argv", ["package.py", "--target", self.target]), contextlib.redirect_stdout(io.StringIO()):
            package.main()
        return self.root / "dist" / f"ods2tsv-{self.version}-{self.target}.zip", binary_name

    def test_packaging_and_verification_agree_for_every_channel_and_target(self):
        for version in ("0.1.1", "0.1.2-alpha.1", "0.1.2-beta.1", "0.1.2-rc.1"):
            for target in ("x86_64-pc-windows-msvc", "x86_64-unknown-linux-musl"):
                with self.subTest(version=version, target=target):
                    self.version, self.target = version, target
                    archive, name = self.build_fixture()
                    with patch.object(artifact, "ROOT", self.root), zipfile.ZipFile(archive) as package_file:
                        artifact.verify_contents(package_file, name, version)
                        guide = package_file.read("README.txt").decode()
                    self.assertIn(f"ODS2TSV {version}", guide)
                    self.assertIn(f"/blob/{version}/docs/FORMAT.md", guide)
                    self.assertIn("Stable release" if "-" not in version else "Experimental " + version.split("-")[1].split(".")[0], guide)

    def test_wrong_channel_and_missing_or_damaged_licenses_fail(self):
        archive, name = self.build_fixture()
        with zipfile.ZipFile(archive) as source:
            members = {entry.filename: source.read(entry) for entry in source.infolist()}
        mutations = (
            ("README.txt", members["README.txt"].replace(b"Stable release", b"Experimental alpha prerelease")),
            ("licenses/rust/licenses/MIT.txt", None),
            ("licenses/rust/licenses/MIT.txt", b""),
            ("LICENSE", b"Incomplete license"),
            ("unexpected.txt", b"Unrelated payload"),
        )
        for member, content in mutations:
            with self.subTest(member=member, content=content), io.BytesIO() as buffer:
                changed = dict(members)
                if content is None:
                    del changed[member]
                else:
                    changed[member] = content
                with zipfile.ZipFile(buffer, "w") as output:
                    for key, value in changed.items():
                        output.writestr(key, value)
                with patch.object(artifact, "ROOT", self.root), zipfile.ZipFile(buffer) as candidate:
                    with self.assertRaises(ValueError):
                        artifact.verify_contents(candidate, name, self.version)

    def test_mismatching_template_and_unknown_versions_fail(self):
        template = (self.root / "docs/PORTABLE.txt").read_text()
        for invalid in (template.replace("@RELEASE_STATUS@", "Stable release"), template + " @UNKNOWN@"):
            with self.assertRaises(ValueError):
                portable_guide(invalid, "0.1.2-alpha.1")
        with self.assertRaisesRegex(ValueError, "Unsupported release version"):
            portable_guide(template, "0.1.2-dev.1")

    def test_checksum_rejection_precedes_any_binary_launch(self):
        archive, _ = self.build_fixture()
        archive.with_suffix(".zip.sha256").write_text("0" * 64 + "  wrong.zip\n", newline="\n")
        with patch.object(artifact.subprocess, "run") as launch, patch("sys.argv", ["artifact.py", str(archive)]):
            with self.assertRaisesRegex(ValueError, "checksum"):
                artifact.main()
            launch.assert_not_called()

    def test_installed_archive_invokes_one_corpus_entry_point(self):
        archive, _ = self.build_fixture()
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            if "--preserve-whitespace" in command:
                destination = Path(command[command.index("-o") + 1])
                destination.mkdir()
                with (destination / "Text.tsv").open("w", encoding="utf-8", newline="") as stream:
                    csv.writer(stream, delimiter="\t").writerows([["  café  text "], ["7" if "--raw" in command else "0007"], ["#DIV/0!"]])
            elif command[0] == "unzip":
                with zipfile.ZipFile(command[2]) as source:
                    source.extractall(command[4])
                (Path(command[4]) / "ods2tsv").chmod(0o755)

        with patch.object(artifact, "ROOT", self.root), patch.object(artifact.subprocess, "run", side_effect=run), \
             patch("sys.argv", ["artifact.py", str(archive)]), contextlib.redirect_stdout(io.StringIO()):
            artifact.main()
        self.assertEqual(sum(Path(command[1]).name == "check.py" for command in calls if len(command) > 1), 1)


class RuntimeGateTest(unittest.TestCase):
    def test_scenario_failure_names_case_and_propagates(self):
        def failure():
            raise ValueError("Deliberately wrong TSV")
        with self.assertRaisesRegex(ValueError, "wrong TSV") as error:
            check.run_scenario("saved/raw case", failure)
        self.assertIn("saved/raw case", " ".join(error.exception.__notes__))

    def test_elf_interpreter_and_shared_dependencies_are_rejected(self):
        for outputs in (("INTERP", ""), ("", "NEEDED")):
            with self.subTest(outputs=outputs), patch.object(dependencies, "os", SimpleNamespace(name="posix")), \
                 patch.object(dependencies.subprocess, "check_output", side_effect=outputs), \
                 patch("sys.argv", ["dependencies.py", "synthetic-binary"]):
                with self.assertRaises(ValueError):
                    dependencies.main()

    def test_windows_unreviewed_or_missing_imports_never_launch_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dumpbin = root / "VC/Tools/MSVC/fixture/bin/Hostx64/x64/dumpbin.exe"
            dumpbin.parent.mkdir(parents=True)
            dumpbin.touch()
            fake_os = SimpleNamespace(name="nt", environ={"ProgramFiles(x86)": str(root)})
            for imports in ("unreviewed-runtime.dll\n", "no imports"):
                with self.subTest(imports=imports), patch.object(dependencies, "os", fake_os), \
                     patch.object(dependencies.subprocess, "check_output", side_effect=[str(root), imports]), \
                     patch.object(dependencies.subprocess, "run") as launch, \
                     patch("sys.argv", ["dependencies.py", "synthetic.exe"]):
                    with self.assertRaises(ValueError):
                        dependencies.main()
                    launch.assert_not_called()

    def test_missing_runtime_inventory_and_wrong_compiler_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.99.1"\n')
            for compiler in ("rustc 0.0.0 (synthetic)", "rustc 1.99.1 (synthetic)"):
                with self.subTest(compiler=compiler), patch.object(licenses, "ROOT", root), \
                     patch.object(licenses.subprocess, "check_output", side_effect=[compiler, str(root)]):
                    with self.assertRaises(ValueError):
                        licenses.runtime_files("x86_64-pc-windows-msvc")

    def test_license_expression_missing_text_and_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "dependency"
            base.mkdir()
            data = {"packages": [{"id": "root"}, {"id": "dep", "name": "synthetic", "version": "1.0",
                                                 "license": "Proprietary", "manifest_path": str(base / "Cargo.toml")}],
                    "resolve": {"root": "root", "nodes": [
                        {"id": "root", "deps": [{"pkg": "dep", "dep_kinds": [{"kind": None}]}]},
                        {"id": "dep", "deps": []}]}}
            for case in ("expression", "missing", "escape"):
                if case != "expression":
                    data["packages"][1]["license"] = "MIT"
                if case == "escape":
                    outside = Path(directory) / "outside.txt"
                    outside.write_text("Synthetic")
                    data["packages"][1]["license_file"] = str(outside)
                with self.subTest(case=case), patch.object(licenses.subprocess, "check_output", return_value=json.dumps(data)):
                    with self.assertRaises(ValueError):
                        licenses.notices("x86_64-pc-windows-msvc")


if __name__ == "__main__":
    unittest.main()
