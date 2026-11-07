"""Execute the shipped Linux binary in Alpine without an installed language runtime."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile

from check import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ods2tsv minimal ") as directory:
        command = ["docker", "run", "--rm", "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
                   "--mount", f"type=bind,source={args.binary.resolve()},target=/app/ods2tsv,readonly",
                   "--mount", f"type=bind,source={ROOT / 'examples/workbook.fods'},target=/input/workbook.fods,readonly",
                   "--mount", f"type=bind,source={directory},target=/out", "alpine:3.23",
                   "/app/ods2tsv", "--output", "/out/export", "/input/workbook.fods"]
        subprocess.run(command, check=True, timeout=120)
        output = Path(directory) / "export"
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        assert [sheet["name"] for sheet in manifest["sheets"]] == ["Zeta", "Empty"]
        assert manifest["sheets"][0]["columns"] == 2
        assert len(manifest["sheets"][0]["merged_ranges"]) == 1
        with (output / "Zeta.tsv").open(encoding="utf-8", newline="") as stream:
            assert list(csv.reader(stream, delimiter="\t")) == [["0007", "0007"]]
        assert (output / "Empty.tsv").read_bytes() == b""
    print("Verified complete export in Alpine 3.23 with network disabled and no language runtime.")


if __name__ == "__main__":
    main()
