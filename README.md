# ODS2TSV

A portable CLI for saved OpenDocument spreadsheet values: one TSV per sheet, with a readable
inventory and JSON manifest preserving sheet order and original merged regions.

## Status

This documents `0.1.0-alpha.1`, the experimental first alpha. See
[releases](https://github.com/viell-dev/slop-ods2tsv/releases) for publication status and downloads,
the [changelog](CHANGELOG.md) for changes, and the
[alpha tracker](https://github.com/viell-dev/slop-ods2tsv/issues/2) for current work. Behavior and
the manifest can change before stable. There is no documentation site: this README, `--help`, and
the [format guide](docs/FORMAT.md) cover the CLI.

This project is written and maintained by AI agents, and no person reviews the code. Tests, CI,
author review, and proportionate independent agent review provide engineering evidence. A person
must try a representative candidate before the first stable release.

## Install update and remove

Download a ZIP and its matching `.sha256` file from
[GitHub releases](https://github.com/viell-dev/slop-ods2tsv/releases):

- Windows 10+ x86-64: `ods2tsv-<version>-x86_64-pc-windows-msvc.zip`.
- Linux x86-64: `ods2tsv-<version>-x86_64-unknown-linux-musl.zip`.

Verify the ZIP with `Get-FileHash <archive> -Algorithm SHA256` in PowerShell, comparing the result
with the checksum file, or `sha256sum -c <archive>.sha256` on Linux. Extract anywhere you can execute
files, using Explorer's **Extract All** on Windows or `unzip <archive>.zip -d ods2tsv` on Linux.
The ZIP preserves Linux executable permissions. No Rust, Python, .NET, LibreOffice, config file,
registry changes, or administrator installation is needed. Add the directory to PATH if desired.

Update by unpacking a verified newer release into a fresh directory and replacing the installed
executable when it is not running. Keep the previous binary for rollback. Remove the installed
files and any PATH entry to uninstall; exported data is not removed.

CI executes Windows binaries on hosted Windows runners and Linux musl binaries on Ubuntu and
Alpine. Other architectures are not verified. Windows alpha executables are unsigned: device
Application Control can block them. Do not bypass security policy; report the exact policy error
or use an environment that permits execution. Hosted CI cannot establish a managed laptop's policy.

## Use

PowerShell, after extracting into the current directory:

```powershell
.\ods2tsv.exe "C:\Data\Workbook.ods"
.\ods2tsv.exe --raw --output "C:\Exports\Workbook" "C:\Data\Workbook.ods"
```

Linux:

```sh
./ods2tsv workbook.ods
./ods2tsv --raw --output exported workbook.fods
```

Without `--output`, creates a fresh timestamped directory under the current working directory.
An explicit destination must be new and its parent must exist. Existing exports are never reused.
On success stdout contains the completed directory path; progress and warnings use stderr. Exit
codes: 0 success, 1 extraction failure, 2 invalid arguments.

Output contains a unique portable `.tsv` per sheet, `manifest.txt`, and `manifest.json`. All sheets
are included in source order, including hidden and empty sheets. Use the manifest for order and
the mapping from original names to filenames. JSON includes dimensions, settings, structured
warnings, and all original merged ranges; see the [guide](docs/FORMAT.md) and
[schema](manifest.schema.json).

Saved cell paragraphs are the default; `--raw` prefers stored unlocalized values. Neither mode
recalculates formulas or renders formats. Leading/interior grid positions and explicit ODF
whitespace survive, merged values fill covered positions, and globally trailing emptiness is
omitted. Every TSV record has the same width. Use a CSV reader configured for tabs, since quoted
fields can contain tabs and newlines.

On failure the tool cleans its own outputs. Interruption or failed cleanup can leave `.incomplete`;
discard that partial export and rerun into a new directory. Consume output only when both manifests
exist and the marker is absent. Save an unencrypted copy of encrypted content before exporting.
For a long-path error, choose a shorter output destination.

## Command reference

CI compares this block with the actual executable.

<!-- help:start -->
```text
Export saved ODS/FODS sheet values to TSV with ordered workbook manifests

Usage: ods2tsv [OPTIONS] <FILE>

Arguments:
  <FILE>  Input OpenDocument spreadsheet (ZIP package or flat XML, detected by content)

Options:
  -r, --raw           Prefer stored values (unlocalized numbers, ISO dates) over saved paragraph text
  -o, --output <DIR>  Create this new output directory instead of a timestamped directory
  -h, --help          Print help
  -V, --version       Print version

Exports every sheet, including hidden and empty sheets. Preserves original coordinates and fills merged cells. Formulas use saved results; they are never recalculated.

Output: one TSV per sheet, manifest.txt, and manifest.json (including original merged ranges). The destination must be new. Without --output, creates a fresh timestamped directory in the current working directory.

Limits: 64 MiB content XML, 10,000,000 rectangular fields per sheet, 1 MiB per cell, 100,000 merged regions per sheet. Encrypted workbook content is unsupported.
```
<!-- help:end -->

## Scope and limits

ODS packages and flat FODS are detected by content; spreadsheet templates with the same structures
are accepted. UTF-8, UTF-16 LE/BE, and ISO-8859-1 XML are tested. At least one sheet must exist;
empty sheets have zero-byte TSVs and zero dimensions. Hidden rows and columns remain data positions;
visibility styles are not resolved into metadata.

The alpha limits decompressed content XML to 64 MiB, cell text to 1 MiB, each sheet's rectangular
output to 10,000,000 fields, and each sheet to 100,000 merged regions. Overflow, invalid counts,
overlapping merges and exceeded limits fail explicitly. Huge empty repeated tails stay compact.
A distant populated cell can still require large output. Limits are fixed alpha safeguards, not a
promise that every input near them fits every computer.

Calculation, styles, charts, annotations, nested tables, tracked history, decryption, Excel formats
and a GUI are outside scope. TSV and this manifest do not form a lossless workbook archive.

## Development reporting and provenance

See [CONTRIBUTING.md](CONTRIBUTING.md) for builds, tests, benchmarks and defect reports,
[SECURITY.md](SECURITY.md) for vulnerabilities, [RELEASING.md](RELEASING.md) for publication,
and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for participation.

The separate [Python](https://github.com/viell-dev/ods_to_tsv.py) and
[Rust](https://github.com/viell-dev/ods2tsv/tree/llm1) prototypes supplied behavioral references
and regression cases; their histories are not imported. The replacement deliberately differs in
leading rows, whitespace, collision-safe naming, rectangularity and complete-document failure
handling. This documented contract is the compatibility reference.

## License

GPL-3.0-only. See [COPYING.md](COPYING.md). Binary ZIPs also contain Cargo dependency notices and
[runtime notices](licenses/README.md).
