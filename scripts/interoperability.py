"""Verify synthetic FODS and real LibreOffice-saved ODS using an isolated application profile."""
import argparse
import csv
import json
from itertools import product
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from validation import require


def calc_import(soffice, profile, source, expected, directory):
    """Use Calc's real text importer; compare its saved/reopened text projection."""
    directory.mkdir()
    imported = directory / "imported"
    reread = directory / "reread"
    imported.mkdir()
    reread.mkdir()
    # All columns Text (format 2), no trim/special-number inference/formula evaluation.
    # Token 13 must be present: omitting it enables formulas for legacy compatibility.
    # https://help.libreoffice.org/latest/en-US/text/shared/guide/csv_params.html
    columns = "/".join(f"{column}/2" for column in range(1, len(expected[0]) + 1))
    settings = f"9,34,76,1,{columns},0,false,false,false,false,false,0,false,false,false"
    subprocess.run([soffice, profile, "--headless", "--infilter=Text - txt - csv (StarCalc):" + settings,
                    "--convert-to", "ods", "--outdir", str(imported), str(source)], check=True, timeout=120)
    workbook = imported / (source.stem + ".ods")
    require(workbook.is_file(), "Calc import did not produce an ODS")
    subprocess.run([soffice, profile, "--headless", "--convert-to",
                    "csv:Text - txt - csv (StarCalc):9,34,76,1,,0,false,true,true,false,false,0,false,false,false",
                    "--outdir", str(reread), str(workbook)], check=True, timeout=120)
    with (reread / (source.stem + ".csv")).open(encoding="utf-8-sig", newline="") as stream:
        actual = list(csv.reader(stream, delimiter="\t"))
    require(actual == expected, f"Calc import/re-read changed TSV values: {actual!r} != {expected!r}")


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
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:of="urn:oasis:names:tc:opendocument:xmlns:of:1.2" xmlns:calcext="urn:org:documentfoundation:names:experimental:calc:xmlns:calcext:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:mimetype="application/vnd.oasis.opendocument.spreadsheet" office:version="1.3">
<office:automatic-styles><style:style style:name="T1" style:family="text"><style:text-properties fo:font-weight="bold"/></style:style></office:automatic-styles>
<office:body><office:spreadsheet><table:table table:name="Zeta">
<table:table-row><table:table-cell office:value-type="string" table:number-columns-spanned="2"><text:p>M</text:p></table:table-cell><table:covered-table-cell/><table:table-cell office:value-type="string"><text:p>café</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell office:value-type="string"><text:p>line1<text:line-break/>line2</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>A<text:tab/>B</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>"quoted"</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell office:value-type="string"><text:p>a<text:tab/> b</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>a<text:s/> b</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>a<text:line-break/><text:s/>b</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell office:value-type="string"><text:p>a<text:line-break/><text:s text:c="2"/>b</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>x<text:s/> y<text:line-break/>z</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p><text:span text:style-name="T1">x</text:span><text:s/> y</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell table:formula="of:=1/0" office:value-type="string" office:string-value="" calcext:value-type="error"><text:p>#DIV/0!</text:p></table:table-cell><table:table-cell table:formula="of:=NA()" office:value-type="string" office:string-value="" calcext:value-type="error"><text:p>#N/A</text:p></table:table-cell><table:table-cell table:formula="of:=&quot;&quot;" office:value-type="string" office:string-value=""><text:p/></table:table-cell></table:table-row>
<table:table-row><table:table-cell table:formula="of:=&quot;a&quot;&amp;CHAR(9)&amp;&quot; b&quot;" office:value-type="string" office:string-value="a&#x09; b"><text:p>a<text:tab/> b</text:p></table:table-cell><table:table-cell/><table:table-cell office:value-type="string"><text:p>tail</text:p></table:table-cell></table:table-row>
<table:table-row table:number-rows-repeated="2"><table:table-cell table:number-columns-repeated="3" office:value-type="string"><text:p>repeat</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell office:value-type="string"><text:p>0007</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>=1+1</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>1E3</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell office:value-type="string"><text:p><text:s text:c="2"/>edges<text:s text:c="2"/></text:p></table:table-cell><table:table-cell/><table:table-cell office:value-type="string"><text:p>tail</text:p></table:table-cell></table:table-row>
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
        require(ods.is_file(), "LibreOffice returned without producing the expected file")
        expected = [["M", "M", "café"], ["line1\nline2", "A\tB", '"quoted"'],
                    ["a\t b", "a  b", "a\n b"], ["a\n  b", "x  y\nz", "x  y"],
                    ["#DIV/0!", "#N/A", ""],
                    ["a\t b", "", "tail"], *[["repeat"] * 3 for _ in range(2)],
                    ["0007", "=1+1", "1E3"], ["  edges  ", "", "tail"]]
        with zipfile.ZipFile(ods) as package:
            tree = ET.fromstring(package.read("content.xml"))
        table_ns = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
        text_ns = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
        whitespace_cell = tree.findall(f".//{table_ns}table-row")[2].findall(f"{table_ns}table-cell")[2]
        paragraphs = whitespace_cell.findall(f"{text_ns}p")
        # Calc emits literal spaces in rich/multi-line cells that it preserves on reopening.
        # Pin both extraction policies against the saved representation and Calc's own re-read.
        normalized_paragraphs = len(paragraphs) == 2 and all(not list(p) for p in paragraphs) and [p.text for p in paragraphs] == ["a", " b"]
        saved_expected = [row[:] for row in expected]
        if normalized_paragraphs:
            saved_expected[2][2] = "a\nb"
            print("Calc emitted a literal paragraph-leading space; applying the ODF paragraph-edge rule.")
        compatibility_cells = tree.findall(f".//{table_ns}table-row")[3].findall(f"{table_ns}table-cell")[:3]
        paragraph_texts = [["".join(p.itertext()) for p in cell.findall(f"{text_ns}p")] for cell in compatibility_cells]
        require(paragraph_texts == [["a", "  b"], ["x  y", "z"], ["x  y"]], f"Calc serialization changed: {paragraph_texts!r}")
        require(all(not cell.findall(f".//{text_ns}s") for cell in compatibility_cells), "Review changed Calc whitespace encoding")
        saved_expected[3] = ["a\nb", "x y\nz", "x y"]
        csv_output = temporary / "calc-reread"
        csv_output.mkdir()
        subprocess.run([soffice, "-env:UserInstallation=" + (temporary / "profile").as_uri(), "--headless",
                        "--convert-to", "csv:Text - txt - csv (StarCalc):9,34,76", "--outdir", str(csv_output), str(ods)], check=True, timeout=120)
        with (csv_output / "source.csv").open(encoding="utf-8-sig", newline="") as stream:
            calc_rows = list(csv.reader(stream, delimiter="\t"))
        require(calc_rows[3] == expected[3], f"Calc re-read changed: {calc_rows[3]!r}")
        print("Calc preserves literal runs; the explicit whitespace option must retain these spaces.")
        for index, workbook in enumerate((source, ods)):
            for raw, preserve in product((False, True), repeat=2):
                destination = temporary / f"export-{index}-{raw}-{preserve}"
                subprocess.run([str(binary), *(["--raw"] if raw else []), *(["--preserve-whitespace"] if preserve else []), "-o", str(destination), str(workbook)], check=True, timeout=60)
                manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
                require(manifest["options"]["preserve_whitespace"] == preserve, 'Whitespace setting differs')
                require([sheet["name"] for sheet in manifest["sheets"]] == ["Zeta", "Alpha"], 'Sheet names or workbook order differ')
                with (destination / manifest["sheets"][0]["file"]).open(encoding="utf-8", newline="") as stream:
                    actual = list(csv.reader(stream, delimiter="\t"))
                require(actual == (saved_expected if workbook == ods and not preserve else expected), f"{workbook.suffix}, raw={raw}, preserve={preserve}: {actual!r}")
                require(manifest["sheets"][0]["merged_ranges"] == [{"start_row": 1, "start_column": 1, "end_row": 1, "end_column": 2}], 'Original merged geometry differs')
                require(all(not sheet["warnings"] for sheet in manifest["sheets"]), 'Unexpected warning metadata')
                require(manifest["sheets"][1]["rows"] == 0, 'Exported row count differs')
                require(manifest["sheets"][1]["columns"] == 0, 'Exported column count differs')
                calc_import(soffice, "-env:UserInstallation=" + (temporary / "import-profile").as_uri(),
                            destination / manifest["sheets"][0]["file"], actual,
                            temporary / f"import-{index}-{raw}-{preserve}")
    print("Verified FODS and LibreOffice-saved ODS in all four value/whitespace modes, plus real Calc TSV import/re-read: text, quoting, errors/empty formula, repeats, coordinates, order, empty sheet and merges. Import uses Text columns with formulas and trimming disabled; it does not test UI or cell-type round trips.")


if __name__ == "__main__":
    main()
