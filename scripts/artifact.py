"""Unpack and execute the actual release archive, preserving Linux ZIP permissions with unzip."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from check import ROOT, corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    archive = args.archive.resolve()
    expected = archive.with_suffix(".zip.sha256").read_text(encoding="utf-8").split()[0]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
    name = "ods2tsv.exe" if os.name == "nt" else "ods2tsv"
    with tempfile.TemporaryDirectory(prefix="ods2tsv installed ") as directory:
        directory = Path(directory)
        with zipfile.ZipFile(archive) as package:
            assert name in package.namelist()
            assert len(package.namelist()) == len(set(package.namelist()))
            for entry in package.infolist():
                assert not Path(entry.filename).is_absolute() and ".." not in Path(entry.filename).parts
                if entry.filename == "THIRD_PARTY_NOTICES.txt":
                    assert package.read(entry).startswith(b"Third-party notices for this target")
                elif entry.filename != name:
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
    print(f"Verified installed archive: {archive.name}")


if __name__ == "__main__":
    main()
