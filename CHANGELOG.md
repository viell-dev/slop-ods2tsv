# Changelog

## 0.1.0-alpha.2

Preserve spaces after explicit ODF whitespace, retain cached error text in raw exports, exclude ruby
annotations/footnote bodies, and allow large ignored XML within the input budget. Cell limits still
fail with cleanup and specific diagnostics. Document covered-cell/anchor-fill semantics.

Buffer decompressed ODS input, add a packaged correctness benchmark, handle closed CLI streams without
panicking, and write LF-only checksums on all platforms. Expand real LibreOffice saved/raw, formula,
whitespace and repeat coverage. [Review and release evidence](https://github.com/viell-dev/slop-ods2tsv/issues/14).
Total output bytes and XML nesting remain [known limits](https://github.com/viell-dev/slop-ods2tsv/issues/9).

## 0.1.0-alpha.1

First experimental alpha: portable Windows/Linux binaries, ODS/FODS saved values, rectangular TSV
with original coordinates, repeats and merge filling, ordered text/JSON manifests with original
merged regions, unique portable filenames, explicit destinations, failure cleanup and resource
budgets. No calculation engine, decryption, GUI or additional spreadsheet formats.
