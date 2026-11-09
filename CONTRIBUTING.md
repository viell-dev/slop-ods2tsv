# Contributing

This is an agent-maintained, MIT-licensed project. Reports from users are welcome without knowledge
of the implementation. Follow the [code of conduct](CODE_OF_CONDUCT.md).

## Reports and scope

Use [issues](https://github.com/viell-dev/slop-ods2tsv/issues). Include `ods2tsv --version`, OS and
architecture, command, expected/actual behavior, and a minimal synthetic workbook. Remove private
values and filenames. Vulnerabilities use [SECURITY.md](SECURITY.md). Enhancements are weighed
against the tool's extraction scope and ongoing support cost; requests are not automatic commitments.
Features and distribution methods excluded from the agreed first-stable goal are not an eventual
roadmap. Evaluate each actual proposal before accepting its long-term maintenance obligations.

Maintainers give each issue/PR one `Type:` and at most one `Status:` from
[the catalog](.github/labels.json). `Needs: Owner`/`Needs: Human` indicate a self-contained request
assigned to the person who must act, using only one Needs label. Optional feedback does not block.

## Build and checks

Reporting a problem needs no build setup. To contribute code, clone this repository, use a task
branch from `main` and run commands from its root. Install Git and
[rustup](https://www.rust-lang.org/tools/install). The repository pins the compiler, rustfmt,
Clippy and rust-analyzer in `rust-toolchain.toml`; `rustup toolchain install` installs that
selection.

- Windows x86-64: install the MSVC C++ build tools and a Windows SDK using
  [Rustup's prerequisites](https://rust-lang.github.io/rustup/installation/windows-msvc.html).
  Use **Developer PowerShell for Visual Studio** targeting x64 when the linker, libraries or SDK
  are not exposed in an ordinary shell. This supplies the session's PATH/LIB/INCLUDE; do not change
  machine-wide paths to repair a single build session.
- Linux: install the native C linker/build tools (Debian/Ubuntu:
  `sudo apt-get install build-essential`) and use the default native Rust target. musl cross-target
  tools are only needed for release ZIPs.

The following Cargo commands work on both platforms. Rust tests and the converter need no Python
or LibreOffice installation.

```sh
cargo build --locked
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo bench --locked --no-run
cargo doc --locked --no-deps
```

Tests construct synthetic ODS/FODS, launch CLI processes, check exact TSV/metadata, exercise XML
encodings/EOF, and compare generated compact grids with simple reference results. New behavior
needs explicit expectations and reproduced defects need regression cases. Preserve failing inputs
and seeds; never retry randomly until green. Required suites fail when fixtures are missing.

Install [Python 3.11+](https://www.python.org/downloads/) for schema, docs and artifact checks.
Create a disposable virtual environment; these commands use its interpreter directly, so shell
activation and execution-policy changes are unnecessary. Windows Developer PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s scripts -p "test_*.py"
.\.venv\Scripts\python.exe -O -m unittest discover -s scripts -p "test_*.py"
.\.venv\Scripts\python.exe -X utf8=0 -O -m unittest discover -s scripts -p "test_*.py"
.\.venv\Scripts\python.exe scripts/check.py --binary target/debug/ods2tsv.exe
```

The forced locale-encoding run matches Windows CI even when Python defaults to UTF-8. It catches
fixtures that accidentally rely on the machine's text encoding.

Linux (install your distribution's `python3-venv` package if venv is unavailable):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py'
.venv/bin/python -O -m unittest discover -s scripts -p 'test_*.py'
.venv/bin/python scripts/check.py --binary target/debug/ods2tsv
```

Use the [maintenance checklist](docs/MAINTENANCE.md) for every affected documentation surface,
automated check and semantic review, including PORTABLE and SECURITY. Wrap prose at 100 columns.
CI checks actual help/version, generated schema-conforming manifests and local Markdown files and
sections; it does not validate arbitrary prose. A documentation site is not required. Coverage
reports expose gaps; percentages alone do not establish correctness. Delete `.venv` to remove
the development environment. Optional benchmarks, Calc and release tools are described below and
in [RELEASING.md](RELEASING.md), separately from the ordinary build/test path.
The release suite uses synthetic archives and simulated external command results to verify channel
selection, notes and failure gates without publishing. It complements actual workflow/download
verification; it is not evidence of GitHub's live behavior by itself.

If device Application Control blocks generated build scripts or unsigned executables, retain the
error and use platform CI evidence. Do not bypass security policy; report actual tested environments.

## Benchmarks and real application checks

`cargo bench --locked --bench extract` measures complete exports over dense flat/packaged, sparse,
repeated, merged and empty-tail synthetic inputs. Inputs and fresh output parents are prepared
outside timed work; conversion includes file/manifest output. Assert dimensions and record commit,
compiler, target, host, fixture size and method. Retain reports and correctness controls. Compare
timings on a controlled host; noisy shared-runner timings are not a hard speed gate.

The archived [parallel-sheet investigation](research/parallel-sheets/README.md) records a bounded
Linux experiment, aggregate measurements, known prototype failures and a synthetic reproduction
kit. Its frozen patch targets the recorded historical commit; it is separate from the supported
exporter and the ordinary regression suite.

`python scripts/interoperability.py --binary <executable>` requires LibreOffice Calc. It saves a
synthetic FODS workbook to ODS in a disposable profile and verifies both. No private workbook or
installed user profile is touched. Linux CI runs it for extraction changes and releases. Artifact
checks and platform dependencies are described in [RELEASING.md](RELEASING.md).
The suite checks saved/raw and collapsed/preserved-whitespace modes, explicit whitespace, cached
errors and valid empty formulas, repeats and geometry. It also imports each non-empty exported TSV
through Calc's real text importer, saves ODS, reopens and compares the text values. All columns use
Text format; formula evaluation, number inference and space trimming are disabled. Leading zeros,
formula-looking strings, Unicode and quoted tabs/newlines are covered. This is headless importer
evidence, not human UI testing or a workbook type/style round trip. When a producer rewrites cell XML,
inspect that representation and apply the documented extraction contract; do not assume round-trip
source text and serialized text are equal.
The repeated-empty benchmark measures source-template scanning separately from necessary output
work. Deterministic tests enforce nesting/output-byte boundaries and cleanup; timings remain
observations rather than shared-runner speed gates.

## Reviews and delivery

PRs describe the problem, resulting behavior, design choices, commands/results, platforms and
evidence limits. Keep issue progress current. Author-review the coherent diff after checks pass,
trying useful inputs outside tests. Release PRs get an independent agent review; identify revision,
scope, findings and dispositions, and verify material fixes. Main requires checks and PRs, with no
administrator bypass. Use GitHub rebase merges for linear history.

Agent-authored issues/PRs/reviews submitted on another person's behalf disclose authorship,
submitting model and harness, and that person's actual review status. Commit messages use
`Assisted-by: <model> via <harness>`, without an email, as their agent attribution trailer. Do not
use agent `Co-Authored-By:` or `Signed-off-by:` trailers. Consumer documentation needs no callout.
