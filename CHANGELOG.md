# Changelog

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
