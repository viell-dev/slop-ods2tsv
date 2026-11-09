"""Check the actual executable, manifest schema, documented help, and Markdown file/section links."""
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

from markdown_links import check_links
from validation import require

ROOT = Path(__file__).resolve().parent.parent
HEADER = (
    '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
    '<office:body><office:spreadsheet>'
)
FOOTER = '</office:spreadsheet></office:body></office:document-content>'
VALUES_WORKBOOK = (
    '<table:table table:name="Zeta"><table:table-row>'
    '<table:table-cell table:number-columns-spanned="2" office:value-type="float" office:value="7">'
    '<text:p>0007</text:p></table:table-cell><table:covered-table-cell/></table:table-row>'
    '<table:table-row><table:table-cell table:formula="of:=1+1"/></table:table-row></table:table>'
    '<table:table table:name="Empty"/>'
)
WHITESPACE_WORKBOOK = (
    '<table:table table:name="Spaces"><table:table-row><table:table-cell>'
    '<text:p>  x  y </text:p></table:table-cell>'
    '<table:table-cell office:value-type="string" office:string-value="attribute">'
    '<text:p>  shown </text:p></table:table-cell></table:table-row></table:table>'
)


def run_scenario(label, function, *args):
    try:
        result = function(*args)
    except Exception as error:
        error.add_note(f"Verification scenario: {label}")
        raise
    print(f"Verified scenario: {label}")
    return result


def schema_validator():
    schema = json.loads((ROOT / "manifest.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return schema, validator


def check_values(binary, directory, source, schema, validator, raw):
    destination = directory / ("raw" if raw else "text")
    command = [str(binary), "--output", str(destination), str(source)]
    if raw:
        command.insert(1, "--raw")
    process = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
    require(process.stdout == f'Exported 2 sheets into "{destination}".\n', 'Unexpected completion message')
    require("warning:" in process.stderr and "Exported" not in process.stderr, 'Expected warning on stderr only')
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    validator.validate(manifest)
    require(manifest["$schema"] == schema["$id"], 'Release-pinned schema URI differs')
    legacy = dict(manifest)
    del legacy["$schema"]
    validator.validate(legacy)
    invalid = dict(manifest, **{"$schema": 42})
    require(not validator.is_valid(invalid), 'Schema accepted invalid metadata')
    require(manifest["options"]["preserve_whitespace"] is False, 'Whitespace setting differs')
    require([sheet["name"] for sheet in manifest["sheets"]] == ["Zeta", "Empty"], 'Sheet names or workbook order differ')
    require(manifest["sheets"][0]["merged_ranges"] == [{"start_row": 1, "start_column": 1, "end_row": 1, "end_column": 2}], 'Original merged geometry differs')
    with (destination / "Zeta.tsv").open(encoding="utf-8", newline="") as stream:
        require(list(csv.reader(stream, delimiter="\t")) == [["7", "7"] if raw else ["0007", "0007"]], 'TSV cell values differ')
    require((destination / "Empty.tsv").read_bytes() == b"", 'Empty sheet must have a zero-byte TSV')
    require(not (destination / ".incomplete").exists(), 'Completed export still has an incomplete marker')
    require(manifest["sheets"][0]["warnings"][0]["code"] == "missing-formula-result", 'Missing formula warning differs')
    check_overview(destination)
    check_existing_destination(command, destination, manifest)
    return manifest


def check_overview(destination):
    overview = (destination / "README.txt").read_text(encoding="utf-8")
    expected_map = ('1. "Zeta" -> "Zeta.tsv"\n2. "Empty" -> "Empty.tsv"\n'
                    '\nMachine-readable details: manifest.json\n')
    require(overview.split("Sheets in original workbook order:\n", 1)[1] == expected_map,
            "Ordered overview mapping differs")
    require("A1:B1" not in overview and "warning:" not in overview and "missing-formula-result" not in overview,
            "Overview contains JSON-only detail")
    require(not (destination / "manifest.txt").exists(), 'Obsolete text manifest exists')


def check_existing_destination(command, destination, manifest):
    rerun = subprocess.run(command, capture_output=True, timeout=30)
    require(rerun.returncode == 1, 'Existing destination was not rejected')
    require(json.loads((destination / "manifest.json").read_text(encoding="utf-8")) == manifest, 'Rejected rerun changed the existing export')


def check_whitespace(binary, directory, source, validator, raw):
    destination = directory / f"preserved-{raw}"
    subprocess.run([str(binary), "--preserve-whitespace", *(["--raw"] if raw else []), "-o", str(destination), str(source)], check=True, capture_output=True, timeout=30)
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    validator.validate(manifest)
    require(manifest["options"]["preserve_whitespace"] is True, 'Whitespace setting differs')
    with (destination / "Spaces.tsv").open(encoding="utf-8", newline="") as stream:
        require(list(csv.reader(stream, delimiter="\t")) == [["  x  y ", "attribute" if raw else "  shown "]], 'TSV cell values differ')


def check_truncation(binary, directory, broken, content):
    with zipfile.ZipFile(broken, "w") as archive:
        archive.writestr("content.xml", content.removesuffix(FOOTER))
    destination = directory / "broken-output"
    require(subprocess.run([str(binary), "-o", str(destination), str(broken)], capture_output=True, timeout=30).returncode == 1, 'Expected operational failure exit code')
    require(not destination.exists(), 'Failed export left an output directory')



def check_closed_stream(binary, directory, source, label, stream, expected_code, failed):
    # Closing the reader before launch makes the broken pipe deterministic on both OSes.
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    destination = directory / label
    streams = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, stream: write_fd}
    try:
        result = subprocess.run([str(binary), "-o", str(destination), str(source)], text=True, timeout=30, **streams)
    finally:
        os.close(write_fd)
    require(result.returncode == expected_code, f"{label}: {result.returncode}, {result.stderr}")
    if not failed:
        require((destination / "manifest.json").is_file() and not (destination / ".incomplete").exists(), 'Completed export still has an incomplete marker')
    else:
        require(not destination.exists(), 'Failed export left an output directory')
    if stream == "stdout":
        require("export completed" in result.stderr and "could not be written" in result.stderr, 'Closed stdout must report a completed export on stderr')
    elif not failed:
        require(result.stdout == f'Exported 2 sheets into "{destination}".\n', "Closed stderr must not suppress completion")


def corpus(binary, directory):
    source = directory / "example with spaces.ods"
    content = HEADER + VALUES_WORKBOOK + FOOTER
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("content.xml", content)
    schema, validator = schema_validator()
    manifest = None
    for raw in (False, True):
        manifest = run_scenario(f"values and metadata raw={raw}",
                                check_values, binary, directory, source, schema, validator, raw)
    whitespace = directory / "whitespace.fods"
    whitespace.write_text(HEADER + WHITESPACE_WORKBOOK + FOOTER, encoding="utf-8")
    for raw in (False, True):
        run_scenario(f"preserved whitespace raw={raw}", check_whitespace,
                     binary, directory, whitespace, validator, raw)
    broken = directory / "broken.ods"
    run_scenario("truncation and cleanup", check_truncation, binary, directory, broken, content)
    for label, stream, expected_code, workbook in (
        ("closed-stdout", "stdout", 1, source),
        ("closed-stderr", "stderr", 0, source),
        ("closed-stderr-error", "stderr", 1, broken),
    ):
        run_scenario(label, check_closed_stream, binary, directory, workbook,
                     label, stream, expected_code, workbook == broken)
    return manifest


def check_metadata(binary, write_help=False):
    version = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))["package"]["version"]
    schema = json.loads((ROOT / "manifest.schema.json").read_text(encoding="utf-8"))
    require(schema["$id"] == f"https://raw.githubusercontent.com/viell-dev/slop-ods2tsv/{version}/manifest.schema.json", 'Release-pinned schema URI differs')
    require(subprocess.check_output([str(binary), "--version"], text=True).strip() == "ods2tsv " + version, 'Executable version differs from Cargo metadata')
    help_text = subprocess.check_output([str(binary), "--help"], text=True).replace("\r\n", "\n").rstrip()
    readme_path = ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    pattern = r'(<!-- help:start -->\n```text\n).*?(\n```\n<!-- help:end -->)'
    if write_help:
        readme, count = re.subn(pattern, lambda match: match[1] + help_text + match[2], readme, flags=re.S)
        require(count == 1, 'Expected exactly one README help block')
        readme_path.write_text(readme, encoding="utf-8", newline="\n")
    else:
        match = re.search(pattern, readme, re.S)
        require(match and match.group(0).split("```text\n", 1)[1].split("\n```", 1)[0] == help_text, "README help differs from executable; use --write-help")
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--write-help", action="store_true")
    args = parser.parse_args()
    binary = args.binary.resolve()
    version = run_scenario("CLI/help/schema/version", check_metadata, binary, args.write_help)
    with tempfile.TemporaryDirectory(prefix="ods2tsv check ") as directory:
        manifest = corpus(binary, Path(directory))
        require(manifest["exporter"]["version"] == version, 'Manifest exporter version differs from Cargo metadata')
    run_scenario("Markdown files and sections", check_links, ROOT)
    print(f"Verified executable {version}, TSV/manifest corpus, schema, README help, and Markdown file/section links.")


if __name__ == "__main__":
    main()
