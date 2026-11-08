# ODS2TSV

A portable CLI for saved OpenDocument spreadsheet values: one TSV per sheet, with a readable
inventory and JSON manifest preserving sheet order and original merged regions.

## Status

This checkout targets `0.1.0-alpha.5`, an experimental alpha. See
[releases](https://github.com/viell-dev/slop-ods2tsv/releases) for publication status and downloads,
the [changelog](CHANGELOG.md) for changes, and the [alpha
tracker](https://github.com/viell-dev/slop-ods2tsv/issues/35) for current work. A source checkout
can include unreleased corrections; use `README.txt` bundled with an installed ZIP for that version's
contract. Behavior and the manifest can change before stable. There is no documentation site: this
README, `--help`, and the [format guide](docs/FORMAT.md) cover the CLI.

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
./ods2tsv --preserve-whitespace --output calc-export workbook.ods
```

The repository provides [examples/workbook.fods](examples/workbook.fods) for sheet order/merges and
[examples/text-options.fods](examples/text-options.fods) for literal spaces, saved/raw numbers and
a cached formula error. Try them with the same commands in a writable directory.

Without `--output`, creates a fresh timestamped directory under the current working directory.
An explicit destination must be new and its parent must exist. Existing exports are never reused.
On success stdout says `Exported 2 sheets into "exported".` with the sheet count and destination;
warnings use stderr. Exit codes: 0 success, 1 operational failure, 2 invalid arguments. If writing
the final completion message to stdout fails, exit 1 leaves the completed export intact; stderr
diagnostics are best-effort.

Output contains a unique portable `.tsv` per sheet, `README.txt`, and `manifest.json`. All sheets
are included in source order, including hidden and empty sheets. Use the manifest for order and
the mapping from original names to filenames. `README.txt` shows settings and that ordered map.
JSON includes dimensions, settings, structured warnings, and all original merged ranges, with a
`$schema` link pinned to the exporter release; see the [guide](docs/FORMAT.md) and
[schema](manifest.schema.json).

Saved cell paragraphs are the default; `--raw` prefers stored unlocalized values. Neither mode
recalculates formulas or renders formats. Cached errors marked by LibreOffice retain their saved
error text in either mode. Leading/interior grid positions and explicit ODF
whitespace survive, merged values fill covered positions, and globally trailing emptiness is
omitted. Every TSV record has the same width. Use a CSV reader configured for tabs, since quoted
fields can contain tabs and newlines.

`--preserve-whitespace` keeps literal spaces inside saved cell paragraphs. Here are the resulting
cell values; surrounding quotes mark the value boundaries and `\n` means a line break:

| Saved cell XML | Default | `--preserve-whitespace` |
| --- | --- | --- |
| `<text:p>  A  B </text:p>` | `"A B"` | `"  A  B "` |
| `<text:p>A</text:p><text:p>  B</text:p>` | `"A\nB"` | `"A\n  B"` |
| `<text:p>A<text:s/>B</text:p>` | `"A B"` | `"A B"` |
| `<text:p>A<text:s/></text:p>` | `"A "` | `"A "` |

Calc can save rich-text/multi-line spaces literally, so use the option to retain them. Explicit
ODF whitespace elements such as `text:s` survive in both modes, including trailing spaces. This
is not a blanket trim option. `--raw` independently chooses the stored value when available; the
whitespace option applies when paragraph text supplies the value. See the
[whitespace contract](docs/FORMAT.md#tsv-values-and-coordinates).

When importing TSV into Calc, choose tabs and double quotes, set all columns to **Text**, and
disable formula evaluation and space trimming. This keeps leading zeros, formula-looking text and
spaces as exported. The automated suite uses Calc's real importer with these settings, then saves
and reopens the result; it checks text values rather than restoring workbook types or styles.

From alpha.5, ZIPs contain the executable, a short `README.txt`, and application/third-party licenses.
Examples, schema, format reference and developer guides stay in this repository. The portable guide
links to the matching release tag. Alpha.5 also replaces `manifest.txt` with `README.txt` and the
bare-path stdout result with a labeled completion message. For automation, choose `--output` and
read its `manifest.json` rather than parsing the human completion message.

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
  -r, --raw                  Prefer stored values (unlocalized numbers, ISO dates) over saved paragraph text
      --preserve-whitespace  Keep literal paragraph whitespace (useful for Calc rich-text and multi-line cells)
  -o, --output <DIR>         Create this new output directory instead of a timestamped directory
  -h, --help                 Print help
  -V, --version              Print version

Exports every sheet, including hidden and empty sheets. Preserves original coordinates and fills merged cells. Formulas use saved results; they are never recalculated.

Output: one TSV per sheet, README.txt (settings and sheet map), and manifest.json (full metadata, including original merged ranges). The destination must be new. Without --output, creates a fresh timestamped directory in the current working directory. Success prints a completion message naming that directory; warnings go to stderr.

Whitespace: literal paragraph text "  A  B " becomes "A B" by default; --preserve-whitespace keeps "  A  B ". Explicit ODF spaces survive both modes. --raw independently prefers stored values over paragraphs.

Limits: 64 MiB content XML, 256 open XML elements, 256 MiB total TSV/manifest bytes, 10,000,000 rectangular fields per sheet, 1 MiB per cell, 100,000 merged regions per sheet. Encrypted workbook content is unsupported.
```
<!-- help:end -->

## Scope and limits

ODS packages and flat FODS are detected by content; spreadsheet templates with the same structures
are accepted. UTF-8, UTF-16 LE/BE, and ISO-8859-1 XML are tested. At least one sheet must exist;
empty sheets have zero-byte TSVs and zero dimensions. Hidden rows and columns remain data positions;
visibility styles are not resolved into metadata.

The alpha limits decompressed content XML to 64 MiB, XML to 256 open elements, cell text to 1 MiB,
each sheet's rectangular output to 10,000,000 fields, and each sheet to 100,000 merged regions.
All TSVs and both manifests together may contain at most 256 MiB of encoded bytes per export;
quoting, separators and record endings count. The temporary incomplete marker is outside that
count. Overflow, invalid counts, overlapping merges and exceeded limits fail explicitly and clean
up owned output. Huge empty repeated tails stay compact. A distant populated cell can still require
large output. These fixed alpha guardrails do not guarantee a CPU/RAM ceiling or that every input
near them fits every computer. Ignored image/annotation content uses the whole-input budget, rather
than the smaller cell-text budget. Package-manifest inspection also enforces the nesting cap.
Retained merged ranges reserve a minimum JSON byte cost while sheets are processed, so excessive
cross-sheet metadata fails before the final manifest write. Actual encoded files still determine
the exact output-byte limit; reservations are not charged twice.

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

MIT. See [LICENSE](LICENSE). The copyright holder authorizes MIT for this implementation, including
adapted material from their prototypes. Binary ZIPs also contain separate Cargo dependency and
[runtime notices](licenses/README.md); those third-party licenses continue to apply.

Alpha.1–alpha.3 were published with GPL-3.0-only notices. The owner selected MIT for alpha.4 and
subsequent releases; the earlier release tags and archives are preserved. The prototype repositories
retain their own historical license files. [Decision and release evidence](https://github.com/viell-dev/slop-ods2tsv/issues/25).
