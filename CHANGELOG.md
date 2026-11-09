# Changelog

## 0.1.1

Harden release and verification checks so Python optimization cannot disable branch, commit, CI,
tag, archive, checksum, license or runtime-import gates. Derive portable-guide status from the
package version for stable and alpha/beta/RC builds. Remove a duplicate installed corpus run and
report named verification scenarios. Check nested documentation and local section links.

Lead the README with installation and first use, document stable/prerelease security support,
Windows/Linux contributor setup, the Rust API boundary and result metadata, and a concrete
documentation synchronization checklist. Reconcile repository labels with the documented catalog.
Converter behavior, CLI options, dependencies, toolchain and manifest schema-1 meanings are
unchanged. Existing human usability and performance evidence remains representative. Windows
binaries remain unsigned and can be refused by device Application Control; this patch does not
change that distribution limit. [Release verification](https://github.com/viell-dev/slop-ods2tsv/issues/56)
and [review findings](https://github.com/viell-dev/slop-ods2tsv/issues/45).

## 0.1.0

First stable release for the agreed Windows/Linux portable CLI. Promote the verified RC.1 with
release version and documentation metadata only: extraction, options, limits, dependencies,
manifest schema 1 and ZIP inventory are unchanged. Existing human usability evidence remains
representative. Each rebuilt platform ZIP is verified for this release. Existing documented limits
continue to apply. Additional features and distribution formats remain subject to scope review.
[Release verification](https://github.com/viell-dev/slop-ods2tsv/issues/38),
[verified candidate](https://github.com/viell-dev/slop-ods2tsv/issues/40),
[agreed goal](https://github.com/viell-dev/slop-ods2tsv/issues/21) and
[human feedback](https://github.com/viell-dev/slop-ods2tsv/issues/22).

## 0.1.0-rc.1

First candidate for the agreed `0.1.0` release. Converter behavior, dependencies, options, limits,
manifest schema 1 and portable ZIP inventory remain unchanged from beta.1.

Support stable publication with the normal GitHub release channel and accurate notes; alpha/beta/RC
remain prereleases. Retain exact-main CI, new-tag and both-platform artifact/integrity gates. Add
ten deterministic publication/channel/failure-gate tests to required CI, without making real
releases during tests. Document RC comparison and version-only stable promotion checks.
[Publisher work](https://github.com/viell-dev/slop-ods2tsv/issues/38),
[review and candidate evidence](https://github.com/viell-dev/slop-ods2tsv/issues/40).

## 0.1.0-beta.1

Enter beta against the agreed first-stable scope after the alpha.5 usability corrections and
focused human feedback. The agreed CLI features are complete; work now focuses on fixes and polish.
Extraction behavior, options, limits, dependency versions and manifest schema 1 are unchanged.
Schema selectors and portable-guide references identify this release tag.

Clarify that excluded features and distribution methods are not future commitments. Each proposed
addition must justify its scope and maintenance/support cost. Retain portable Windows/Linux ZIPs.
This release makes no performance-fix claim; the non-reproduced timing observation retains its
evidence and limitations in the linked investigation.
[Goal agreement](https://github.com/viell-dev/slop-ods2tsv/issues/21),
[completed human feedback](https://github.com/viell-dev/slop-ods2tsv/issues/22),
[timing investigation](https://github.com/viell-dev/slop-ods2tsv/issues/26),
[review and release evidence](https://github.com/viell-dev/slop-ods2tsv/issues/37).

## 0.1.0-alpha.5

Make export completion identify the sheet count and destination on stdout. Warnings stay on stderr.
This replaces the earlier bare-path stdout result; automation should choose `--output` and read
`manifest.json` in that directory.

Replace the exported `manifest.txt` with `README.txt`: settings and the sheet-name-to-file map in
workbook order. Dimensions, warnings and merged ranges remain complete in JSON. Add a `$schema`
selector pinned to this release's schema `$id`, keeping older schema-1 manifests valid.

Explain whitespace policies with concrete values and XML examples; conversion behavior is unchanged.
Check exported TSV with Calc's real text importer and save/re-read, including leading zeros,
formula-looking strings, explicit spaces and quoted tabs/newlines. Use Text columns with formula
evaluation and trimming disabled; this checks the text projection, not workbook types/styles.

Reduce portable ZIPs to the binary, short `README.txt` and complete application/third-party licenses.
Versioned reference/schema/examples and developer documentation stay in the repository.
[Review and release evidence](https://github.com/viell-dev/slop-ods2tsv/issues/35).
[Human usability feedback and follow-up](https://github.com/viell-dev/slop-ods2tsv/issues/22).

## 0.1.0-alpha.4

Adopt the owner's selected MIT license for the application, including authorized prototype-derived
material. Replace the application GPL file with `LICENSE`, update Cargo metadata and public guides,
and verify that portable ZIPs carry MIT alongside the unchanged third-party notices.

Conversion behavior, options and manifest schema remain the same as alpha.3. Earlier release tags
and archives keep their original notices. [Decision and release evidence](https://github.com/viell-dev/slop-ods2tsv/issues/25).
[Human installation/use request before stable](https://github.com/viell-dev/slop-ods2tsv/issues/22).

## 0.1.0-alpha.3

Add `--preserve-whitespace` for literal cell-paragraph text, including Calc rich-text/multi-line
spaces, in either saved/raw mode. The default keeps ODF collapsing. Both manifests record the
choice with an additive schema-1 field; real Calc save/re-read checks cover both policies.

Retain meaningful cached-error paragraphs or a non-whitespace attribute fallback; warn for error
formulas whose only saved text is whitespace. Keep read/checksum/budget failures distinct from
positioned XML syntax errors without a second validation pass. Character-decoding failures omit
unknown positions rather than displaying a fabricated `1:1`.

Cap XML at 256 open elements and combined TSV/manifest output at 256 MiB per export, including
encoded quoting and separators. Reserve a minimum JSON byte cost for retained merged ranges
during sheet processing, then count actual manifest writes without double charging. Prune empty
source templates and cache non-empty repeated-row cells. Add actual-limit cleanup tests and a
repeated-empty benchmark. These caps remain guardrails,
not fixed CPU/RAM guarantees. Windows/Linux portable ZIPs remain the installation path.
[Review and release evidence](https://github.com/viell-dev/slop-ods2tsv/issues/19).
[Human installation/use request before stable](https://github.com/viell-dev/slop-ods2tsv/issues/22).

## 0.1.0-alpha.2

Preserve spaces after explicit ODF whitespace, retain cached error text in raw exports, exclude ruby
annotations/footnote bodies, and allow large ignored XML within the input budget. Cell limits still
fail with cleanup and specific diagnostics. Document covered-cell/anchor-fill semantics.

Buffer decompressed ODS input, add a packaged correctness benchmark, handle closed CLI streams
without panicking, and write LF-only checksums on all platforms. Expand real LibreOffice saved/raw,
formula, whitespace and repeat coverage. [Review and release evidence](https://github.com/viell-dev/slop-ods2tsv/issues/14).
Total output bytes and XML nesting remain [known limits](https://github.com/viell-dev/slop-ods2tsv/issues/9).
Strict ODF whitespace collapsing can still lose spaces that Calc preserves in rich-text/multi-line
cells; this [compatibility limit](https://github.com/viell-dev/slop-ods2tsv/issues/16) is now disclosed
and covered by real-application checks.

## 0.1.0-alpha.1

First experimental alpha: portable Windows/Linux binaries, ODS/FODS saved values, rectangular TSV
with original coordinates, repeats and merge filling, ordered text/JSON manifests with original
merged regions, unique portable filenames, explicit destinations, failure cleanup and resource
budgets. No calculation engine, decryption, GUI or additional spreadsheet formats.
