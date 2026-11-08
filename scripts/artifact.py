"""Unpack and execute the actual release archive, preserving Linux ZIP permissions with unzip."""
import argparse
import csv
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import zipfile

from check import ROOT, corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    archive = args.archive.resolve()
    checksum = archive.with_suffix(".zip.sha256").read_bytes()
    assert checksum.endswith(b"\n") and b"\r" not in checksum, "Checksum sidecar must use LF on every platform"
    expected = checksum.decode("utf-8").split()[0]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
    name = "ods2tsv.exe" if os.name == "nt" else "ods2tsv"
    with tempfile.TemporaryDirectory(prefix="ods2tsv installed ") as directory:
        directory = Path(directory)
        with zipfile.ZipFile(archive) as package:
            assert name in package.namelist()
            required = {"THIRD_PARTY_NOTICES.txt", "licenses/README.md",
                        "licenses/rust/COPYRIGHT-library.html", "licenses/rust/licenses/MIT.txt",
                        "licenses/rust/licenses/Apache-2.0.txt", "README.txt", "LICENSE"}
            if os.name != "nt":
                required.add("licenses/musl-1.2.5.COPYRIGHT")
            assert required <= set(package.namelist()), "Missing dependency/runtime license inventory"
            allowed = {name, "README.txt", "LICENSE", "THIRD_PARTY_NOTICES.txt", "licenses/README.md"}
            if os.name != "nt":
                allowed.add("licenses/musl-1.2.5.COPYRIGHT")
            assert all(entry in allowed or entry == "licenses/rust/COPYRIGHT-library.html"
                       or entry.startswith("licenses/rust/licenses/") for entry in package.namelist()), "Portable ZIP contains unrelated repository files"
            version = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))["package"]["version"]
            portable_readme = (ROOT / "docs/PORTABLE.txt").read_text(encoding="utf-8").replace("@VERSION@", version)
            assert package.read("README.txt") == portable_readme.encode("utf-8")
            assert "@VERSION@" not in portable_readme
            application_license = package.read("LICENSE").decode("utf-8").replace("\r\n", "\n")
            assert application_license.startswith("MIT License\n\nCopyright (c) 2026 viell\n")
            assert "Permission is hereby granted, free of charge" in application_license
            license_words = " ".join(application_license.split())
            assert "The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software." in license_words
            assert 'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED' in license_words
            assert "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE." in license_words
            assert b"Copyright notices for The Rust Standard Library" in package.read("licenses/rust/COPYRIGHT-library.html")
            assert len(package.namelist()) == len(set(package.namelist()))
            for entry in package.infolist():
                assert not Path(entry.filename).is_absolute() and ".." not in Path(entry.filename).parts
                if entry.filename == "THIRD_PARTY_NOTICES.txt":
                    assert package.read(entry).startswith(b"Third-party notices for this target")
                elif entry.filename.startswith("licenses/rust/"):
                    assert package.read(entry).strip(), "Empty Rust runtime notice"
                elif entry.filename not in (name, "README.txt"):
                    assert package.read(entry) == (ROOT / entry.filename).read_bytes(), entry.filename
            if os.name == "nt":
                package.extractall(directory)
            else:
                assert package.getinfo(name).external_attr >> 16 & 0o111
        if os.name != "nt":
            subprocess.run(["unzip", "-q", str(archive), "-d", str(directory)], check=True)
            assert os.access(directory / name, os.X_OK)
        binary = directory / name
        subprocess.run([sys.executable, str(ROOT / "scripts/check.py"), "--binary", str(binary)], check=True)
        subprocess.run([sys.executable, str(ROOT / "scripts/dependencies.py"), str(binary)], check=True)
        corpus(binary, directory)
        for raw in (False, True):
            destination = directory / f"example-text-{raw}"
            subprocess.run([str(binary), "--preserve-whitespace", *(["--raw"] if raw else []), "-o", str(destination), str(ROOT / "examples/text-options.fods")], check=True, capture_output=True, timeout=30)
            with (destination / "Text.tsv").open(encoding="utf-8", newline="") as stream:
                assert list(csv.reader(stream, delimiter="\t")) == [["  café  text "], ["7" if raw else "0007"], ["#DIV/0!"]]
    print(f"Verified installed archive: {archive.name}")


if __name__ == "__main__":
    main()
