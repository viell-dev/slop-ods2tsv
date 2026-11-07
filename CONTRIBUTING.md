# Contributing

This is an agent-maintained, GPL-3.0-only project. Reports from users are welcome without knowledge
of the implementation. Follow the [code of conduct](CODE_OF_CONDUCT.md).

## Reports and scope

Use [issues](https://github.com/viell-dev/slop-ods2tsv/issues). Include `ods2tsv --version`, OS and
architecture, command, expected/actual behavior, and a minimal synthetic workbook. Remove private
values and filenames. Vulnerabilities use [SECURITY.md](SECURITY.md). Enhancements are weighed
against the tool's extraction scope and ongoing support cost; requests are not automatic commitments.

Maintainers give each issue/PR one `Type:` and at most one `Status:` from
[the catalog](.github/labels.json). `Needs: Owner`/`Needs: Human` indicate a self-contained request
assigned to the person who must act, using only one Needs label. Optional feedback does not block.

## Build and checks

Clone this repository and run commands from its root. Install rustup and native build tools.
The repository pins its compiler, rustfmt, Clippy and
rust-analyzer. Use a task branch from `main`. Rust tests and the converter need no Python or
LibreOffice installation.

```sh
cargo build --locked
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo bench --locked --no-run
```

Tests construct synthetic ODS/FODS, launch CLI processes, check exact TSV/metadata, exercise XML
encodings/EOF, and compare generated compact grids with simple reference results. New behavior
needs explicit expectations and reproduced defects need regression cases. Preserve failing inputs
and seeds; never retry randomly until green. Required suites fail when fixtures are missing.

Python 3.11+ supports schema, docs and artifact checks. In an isolated environment:

```sh
python -m pip install -r requirements-dev.txt
python scripts/check.py --binary target/debug/ods2tsv
```

Use `.exe` on Windows. After intentionally changing help, add `--write-help`, review the README
diff, and rerun without it. CI checks actual help, version, generated schema-conforming manifests
and local Markdown file links. Update public prose/examples with behavior changes and wrap prose
at 100 columns. A documentation site is not required. Coverage reports expose gaps; percentages
alone do not establish correctness.

If device Application Control blocks generated build scripts or unsigned executables, retain the
error and use platform CI evidence. Do not bypass security policy; report actual tested environments.

## Benchmarks and real application checks

`cargo bench --locked --bench extract` measures complete exports over dense, sparse, repeated,
merged and empty-tail synthetic inputs. Inputs and fresh output parents are prepared outside timed
work; conversion includes file/manifest output. Assert dimensions and record commit, compiler,
target, host, fixture size and method. Retain reports and correctness controls. Compare timings on
a controlled host; noisy shared-runner timings are not a hard speed gate.

`python scripts/interoperability.py --binary <executable>` requires LibreOffice Calc. It saves a
synthetic FODS workbook to ODS in a disposable profile and verifies both. No private workbook or
installed user profile is touched. Linux CI runs it for extraction changes and releases. Artifact
checks and platform dependencies are described in [RELEASING.md](RELEASING.md).

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
