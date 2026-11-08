"""Check the actual executable, manifest schema, documented help, and Markdown file links."""
import argparse
import csv
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib
import zipfile

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
HEADER = '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:spreadsheet>'
FOOTER = '</office:spreadsheet></office:body></office:document-content>'


def corpus(binary, directory):
    source = directory / "example with spaces.ods"
    content = HEADER + '<table:table table:name="Zeta"><table:table-row><table:table-cell table:number-columns-spanned="2" office:value-type="float" office:value="7"><text:p>0007</text:p></table:table-cell><table:covered-table-cell/></table:table-row><table:table-row><table:table-cell table:formula="of:=1+1"/></table:table-row></table:table><table:table table:name="Empty"/>' + FOOTER
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("content.xml", content)
    schema = json.loads((ROOT / "manifest.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    last_manifest = None
    for raw in (False, True):
        destination = directory / ("raw" if raw else "text")
        command = [str(binary), "--output", str(destination), str(source)]
        if raw:
            command.insert(1, "--raw")
        process = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        assert process.stdout == f'Exported 2 sheets into "{destination}".\n'
        assert "warning:" in process.stderr and "Exported" not in process.stderr
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        validator.validate(manifest)
        assert manifest["$schema"] == schema["$id"]
        legacy = dict(manifest)
        del legacy["$schema"]
        validator.validate(legacy)
        invalid = dict(manifest, **{"$schema": 42})
        assert not validator.is_valid(invalid)
        assert manifest["options"]["preserve_whitespace"] is False
        assert [sheet["name"] for sheet in manifest["sheets"]] == ["Zeta", "Empty"]
        assert manifest["sheets"][0]["merged_ranges"] == [{"start_row": 1, "start_column": 1, "end_row": 1, "end_column": 2}]
        with (destination / "Zeta.tsv").open(encoding="utf-8", newline="") as stream:
            assert list(csv.reader(stream, delimiter="\t")) == [["7", "7"] if raw else ["0007", "0007"]]
        assert (destination / "Empty.tsv").read_bytes() == b""
        assert not (destination / ".incomplete").exists()
        assert manifest["sheets"][0]["warnings"][0]["code"] == "missing-formula-result"
        overview = (destination / "README.txt").read_text(encoding="utf-8")
        assert overview.split("Sheets in original workbook order:\n", 1)[1] == '1. "Zeta" -> "Zeta.tsv"\n2. "Empty" -> "Empty.tsv"\n\nMachine-readable details: manifest.json\n'
        assert "A1:B1" not in overview and "warning:" not in overview and "missing-formula-result" not in overview
        assert not (destination / "manifest.txt").exists()
        rerun = subprocess.run(command, capture_output=True, timeout=30)
        assert rerun.returncode == 1
        assert json.loads((destination / "manifest.json").read_text(encoding="utf-8")) == manifest
        last_manifest = manifest
    whitespace = directory / "whitespace.fods"
    whitespace.write_text(HEADER + '<table:table table:name="Spaces"><table:table-row><table:table-cell><text:p>  x  y </text:p></table:table-cell><table:table-cell office:value-type="string" office:string-value="attribute"><text:p>  shown </text:p></table:table-cell></table:table-row></table:table>' + FOOTER, encoding="utf-8")
    for raw in (False, True):
        destination = directory / f"preserved-{raw}"
        subprocess.run([str(binary), "--preserve-whitespace", *(["--raw"] if raw else []), "-o", str(destination), str(whitespace)], check=True, capture_output=True, timeout=30)
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        validator.validate(manifest)
        assert manifest["options"]["preserve_whitespace"] is True
        with (destination / "Spaces.tsv").open(encoding="utf-8", newline="") as stream:
            assert list(csv.reader(stream, delimiter="\t")) == [["  x  y ", "attribute" if raw else "  shown "]]
    broken = directory / "broken.ods"
    with zipfile.ZipFile(broken, "w") as archive:
        archive.writestr("content.xml", content.removesuffix(FOOTER))
    destination = directory / "broken-output"
    assert subprocess.run([str(binary), "-o", str(destination), str(broken)], capture_output=True, timeout=30).returncode == 1
    assert not destination.exists()
    # The reader is closed before launch, making broken-pipe behavior deterministic on both OSes.
    for label, stream, expected_code, workbook in (
        ("closed-stdout", "stdout", 1, source),
        ("closed-stderr", "stderr", 0, source),
        ("closed-stderr-error", "stderr", 1, broken),
    ):
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        destination = directory / label
        streams = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, stream: write_fd}
        try:
            result = subprocess.run([str(binary), "-o", str(destination), str(workbook)], text=True, timeout=30, **streams)
        finally:
            os.close(write_fd)
        assert result.returncode == expected_code, f"{label}: {result.returncode}, {result.stderr}"
        if workbook == source:
            assert (destination / "manifest.json").is_file() and not (destination / ".incomplete").exists()
        else:
            assert not destination.exists()
        if stream == "stdout":
            assert "export completed" in result.stderr and "could not be written" in result.stderr
        elif workbook == source:
            assert result.stdout == f'Exported 2 sheets into "{destination}".\n', "Closed stderr must not suppress completion"
    return last_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--write-help", action="store_true")
    args = parser.parse_args()
    binary = args.binary.resolve()
    version = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))["package"]["version"]
    schema = json.loads((ROOT / "manifest.schema.json").read_text(encoding="utf-8"))
    assert schema["$id"] == f"https://raw.githubusercontent.com/viell-dev/slop-ods2tsv/{version}/manifest.schema.json"
    assert subprocess.check_output([str(binary), "--version"], text=True).strip() == "ods2tsv " + version
    help_text = subprocess.check_output([str(binary), "--help"], text=True).replace("\r\n", "\n").rstrip()
    readme_path = ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    pattern = r'(<!-- help:start -->\n```text\n).*?(\n```\n<!-- help:end -->)'
    if args.write_help:
        readme, count = re.subn(pattern, lambda match: match[1] + help_text + match[2], readme, flags=re.S)
        assert count == 1
        readme_path.write_text(readme, encoding="utf-8", newline="\n")
    else:
        match = re.search(pattern, readme, re.S)
        assert match and match.group(0).split("```text\n", 1)[1].split("\n```", 1)[0] == help_text, "README help differs from executable; use --write-help"
    with tempfile.TemporaryDirectory(prefix="ods2tsv check ") as directory:
        manifest = corpus(binary, Path(directory))
        assert manifest["exporter"]["version"] == version
    for path in [*ROOT.glob("*.md"), *ROOT.glob("docs/*.md"), *ROOT.glob("licenses/*.md")]:
        text = re.sub(r'```.*?```', '', path.read_text(encoding="utf-8"), flags=re.S)
        for link in re.findall(r'\]\(([^)]+)\)', text):
            if "://" in link or link.startswith("#") or link.startswith("mailto:"):
                continue
            target = link.split("#", 1)[0].strip("<>")
            assert (path.parent / target).exists(), f"Broken local link in {path.name}: {link}"
    print(f"Verified executable {version}, TSV/manifest corpus, schema, README help, and Markdown file links.")


if __name__ == "__main__":
    main()
