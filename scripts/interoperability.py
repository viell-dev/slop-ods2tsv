"""Verify synthetic FODS and real LibreOffice-saved ODS using an isolated application profile."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("LibreOffice Calc is required; this suite must not silently skip")
    print(subprocess.check_output([soffice, "--version"], text=True).strip())
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:of="urn:oasis:names:tc:opendocument:xmlns:of:1.2" xmlns:calcext="urn:org:documentfoundation:names:experimental:calc:xmlns:calcext:1.0" office:mimetype="application/vnd.oasis.opendocument.spreadsheet" office:version="1.3">
<office:body><office:spreadsheet><table:table table:name="Zeta">
<table:table-row><table:table-cell office:value-type="string" table:number-columns-spanned="2"><text:p>M</text:p></table:table-cell><table:covered-table-cell/><table:table-cell office:value-type="string"><text:p>café</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell office:value-type="string"><text:p>line1<text:line-break/>line2</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>A<text:tab/>B</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>"quoted"</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell office:value-type="string"><text:p>a<text:tab/> b</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>a<text:s/> b</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>a<text:line-break/><text:s/>b</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell table:formula="of:=1/0" office:value-type="string" office:string-value="" calcext:value-type="error"><text:p>#DIV/0!</text:p></table:table-cell><table:table-cell table:formula="of:=NA()" office:value-type="string" office:string-value="" calcext:value-type="error"><text:p>#N/A</text:p></table:table-cell><table:table-cell table:formula="of:=&quot;&quot;" office:value-type="string" office:string-value=""><text:p/></table:table-cell></table:table-row>
<table:table-row><table:table-cell table:formula="of:=&quot;a&quot;&amp;CHAR(9)&amp;&quot; b&quot;" office:value-type="string" office:string-value="a&#x09; b"><text:p>a<text:tab/> b</text:p></table:table-cell><table:table-cell/><table:table-cell office:value-type="string"><text:p>tail</text:p></table:table-cell></table:table-row>
<table:table-row table:number-rows-repeated="2"><table:table-cell table:number-columns-repeated="3" office:value-type="string"><text:p>repeat</text:p></table:table-cell></table:table-row>
</table:table><table:table table:name="Alpha"><table:table-row/></table:table></office:spreadsheet></office:body></office:document>'''
    with tempfile.TemporaryDirectory(prefix="ods2tsv libreoffice ") as temporary:
        temporary = Path(temporary)
        source = temporary / "source.fods"
        source.write_text(content, encoding="utf-8")
        saved = temporary / "saved"
        saved.mkdir()
        command = [soffice, "-env:UserInstallation=" + (temporary / "profile").as_uri(), "--headless",
                   "--convert-to", "ods", "--outdir", str(saved), str(source)]
        subprocess.run(command, check=True, timeout=120)
        ods = saved / "source.ods"
        assert ods.is_file(), "LibreOffice returned without producing the expected file"
        expected = [["M", "M", "café"], ["line1\nline2", "A\tB", '"quoted"'],
                    ["a\t b", "a  b", "a\n b"], ["#DIV/0!", "#N/A", ""],
                    ["a\t b", "", "tail"], *[["repeat"] * 3 for _ in range(2)]]
        with zipfile.ZipFile(ods) as package:
            tree = ET.fromstring(package.read("content.xml"))
        table_ns = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
        text_ns = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
        whitespace_cell = tree.findall(f".//{table_ns}table-row")[2].findall(f"{table_ns}table-cell")[2]
        paragraphs = whitespace_cell.findall(f"{text_ns}p")
        # Calc 25.2 rewrites this cell to <text:p>a</text:p><text:p> b</text:p>.
        # ODF 6.1.2 removes that literal paragraph-leading space. Keep the source FODS expectation;
        # accept this one inspected producer representation, not arbitrary round-trip differences.
        normalized_paragraphs = len(paragraphs) == 2 and all(not list(p) for p in paragraphs) and [p.text for p in paragraphs] == ["a", " b"]
        saved_expected = [row[:] for row in expected]
        if normalized_paragraphs:
            saved_expected[2][2] = "a\nb"
            print("Calc emitted a literal paragraph-leading space; applying the ODF paragraph-edge rule.")
        for index, workbook in enumerate((source, ods)):
            for raw in (False, True):
                destination = temporary / f"export-{index}-{raw}"
                subprocess.run([str(binary), *(["--raw"] if raw else []), "-o", str(destination), str(workbook)], check=True, timeout=60)
                manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
                assert [sheet["name"] for sheet in manifest["sheets"]] == ["Zeta", "Alpha"]
                with (destination / manifest["sheets"][0]["file"]).open(encoding="utf-8", newline="") as stream:
                    actual = list(csv.reader(stream, delimiter="\t"))
                assert actual == (saved_expected if workbook == ods else expected), f"{workbook.suffix}, raw={raw}: {actual!r}"
                assert manifest["sheets"][0]["merged_ranges"] == [{"start_row": 1, "start_column": 1, "end_row": 1, "end_column": 2}]
                assert all(not sheet["warnings"] for sheet in manifest["sheets"])
                assert manifest["sheets"][1]["rows"] == 0
                assert manifest["sheets"][1]["columns"] == 0
    print("Verified FODS and LibreOffice-saved ODS in saved/raw modes: text, errors/empty formula, repeats, coordinates, order, empty sheet and merges.")


if __name__ == "__main__":
    main()
