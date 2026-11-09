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

from check import ROOT
from release_metadata import portable_guide

from validation import require



def verify_contents(package, name, version):
    require(name in package.namelist(), 'Archive has no target executable')
    required = {"THIRD_PARTY_NOTICES.txt", "licenses/README.md",
                "licenses/rust/COPYRIGHT-library.html", "licenses/rust/licenses/MIT.txt",
                "licenses/rust/licenses/Apache-2.0.txt", "README.txt", "LICENSE"}
    if name != "ods2tsv.exe":
        required.add("licenses/musl-1.2.5.COPYRIGHT")
    require(required <= set(package.namelist()), "Missing dependency/runtime license inventory")
    allowed = {name, "README.txt", "LICENSE", "THIRD_PARTY_NOTICES.txt", "licenses/README.md"}
    if name != "ods2tsv.exe":
        allowed.add("licenses/musl-1.2.5.COPYRIGHT")
    require(all(entry in allowed or entry == "licenses/rust/COPYRIGHT-library.html"
               or entry.startswith("licenses/rust/licenses/") for entry in package.namelist()), "Portable ZIP contains unrelated repository files")
    portable_readme = portable_guide((ROOT / "docs/PORTABLE.txt").read_text(encoding="utf-8"), version)
    require(package.read("README.txt") == portable_readme.encode("utf-8"), 'Portable guide differs from version-derived template')
    require("@VERSION@" not in portable_readme, 'Portable guide contains an unresolved version')
    application_license = package.read("LICENSE").decode("utf-8").replace("\r\n", "\n")
    require(application_license.startswith("MIT License\n\nCopyright (c) 2026 viell\n"), 'Application MIT license header or grant differs')
    require("Permission is hereby granted, free of charge" in application_license, 'Application MIT license header or grant differs')
    license_words = " ".join(application_license.split())
    require("The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software." in license_words, 'Application MIT license is incomplete')
    require('THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED' in license_words, 'Application MIT license is incomplete')
    require("OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE." in license_words, 'Application MIT license is incomplete')
    require(b"Copyright notices for The Rust Standard Library" in package.read("licenses/rust/COPYRIGHT-library.html"), 'Rust standard-library inventory differs')
    require(len(package.namelist()) == len(set(package.namelist())), 'Archive contains duplicate member names')
    for entry in package.infolist():
        require(not Path(entry.filename).is_absolute() and ".." not in Path(entry.filename).parts, 'Archive member path is unsafe')
        if entry.filename == "THIRD_PARTY_NOTICES.txt":
            require(package.read(entry).startswith(b"Third-party notices for this target"), 'Archive license bytes differ from repository')
        elif entry.filename.startswith("licenses/rust/"):
            require(package.read(entry).strip(), "Empty Rust runtime notice")
        elif entry.filename not in (name, "README.txt"):
            require(package.read(entry) == (ROOT / entry.filename).read_bytes(), entry.filename)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    archive = args.archive.resolve()
    checksum = archive.with_suffix(".zip.sha256").read_bytes()
    require(checksum.endswith(b"\n") and b"\r" not in checksum, "Checksum sidecar must use LF on every platform")
    expected = checksum.decode("utf-8").split()[0]
    require(hashlib.sha256(archive.read_bytes()).hexdigest() == expected, 'Archive checksum differs')
    version = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))["package"]["version"]
    name = "ods2tsv.exe" if os.name == "nt" else "ods2tsv"
    with tempfile.TemporaryDirectory(prefix="ods2tsv installed ") as directory:
        directory = Path(directory)
        with zipfile.ZipFile(archive) as package:
            verify_contents(package, name, version)
            if os.name == "nt":
                package.extractall(directory)
            else:
                require(package.getinfo(name).external_attr >> 16 & 0o111, 'Linux executable permission is missing in ZIP')
        if os.name != "nt":
            subprocess.run(["unzip", "-q", str(archive), "-d", str(directory)], check=True)
            require(os.access(directory / name, os.X_OK), 'Extracted Linux binary is not executable')
        binary = directory / name
        subprocess.run([sys.executable, str(ROOT / "scripts/check.py"), "--binary", str(binary)], check=True)
        subprocess.run([sys.executable, str(ROOT / "scripts/dependencies.py"), str(binary)], check=True)
        for raw in (False, True):
            destination = directory / f"example-text-{raw}"
            subprocess.run([str(binary), "--preserve-whitespace", *(["--raw"] if raw else []), "-o", str(destination), str(ROOT / "examples/text-options.fods")], check=True, capture_output=True, timeout=30)
            with (destination / "Text.tsv").open(encoding="utf-8", newline="") as stream:
                require(list(csv.reader(stream, delimiter="\t")) == [["  café  text "], ["7" if raw else "0007"], ["#DIV/0!"]], f"Installed text example differs: raw={raw}")
    print(f"Verified installed archive: {archive.name}")


if __name__ == "__main__":
    main()
