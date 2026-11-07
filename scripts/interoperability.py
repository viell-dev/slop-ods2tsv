"""Verify synthetic FODS and real LibreOffice-saved ODS using an isolated application profile."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


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
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:mimetype="application/vnd.oasis.opendocument.spreadsheet" office:version="1.3">
<office:body><office:spreadsheet><table:table table:name="Zeta">
<table:table-row><table:table-cell office:value-type="string" table:number-columns-spanned="2"><text:p>M</text:p></table:table-cell><table:covered-table-cell/><table:table-cell office:value-type="string"><text:p>café</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell office:value-type="string"><text:p>line1<text:line-break/>line2</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>A<text:tab/>B</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>"quoted"</text:p></table:table-cell></table:table-row>
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
        for index, workbook in enumerate((source, ods)):
            destination = temporary / f"export-{index}"
            subprocess.run([str(binary), "-o", str(destination), str(workbook)], check=True, timeout=60)
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            assert [sheet["name"] for sheet in manifest["sheets"]] == ["Zeta", "Alpha"]
            with (destination / manifest["sheets"][0]["file"]).open(encoding="utf-8", newline="") as stream:
                assert list(csv.reader(stream, delimiter="\t")) == [["M", "M", "café"], ["line1\nline2", "A\tB", '"quoted"']]
            assert manifest["sheets"][0]["merged_ranges"] == [{"start_row": 1, "start_column": 1, "end_row": 1, "end_column": 2}]
            assert manifest["sheets"][1]["rows"] == 0
            assert manifest["sheets"][1]["columns"] == 0
    print("Verified original FODS and LibreOffice-saved ODS contents, coordinates, order, empty sheet, and merge metadata.")


if __name__ == "__main__":
    main()
