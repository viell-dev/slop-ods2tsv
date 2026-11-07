# Export format

This describes the `0.1.0-alpha.2` source and manifest schema 1; GitHub releases determine which
builds are published. CLI help is reproduced in the [README](../README.md#command-reference).

## TSV values and coordinates

UTF-8 without a BOM; tabs; CRLF records; necessary double quoting with literal quotes doubled.
Embedded tabs and line breaks remain inside one quoted field. Every record has the sheet's final
exported width. The rectangle starts at original A1 and ends at the final non-empty position after
merge fill. Leading and interior empty positions survive; globally trailing emptiness does not.
An empty sheet has a zero-byte TSV and zero dimensions. A value only at C3 produces a three-by-three
rectangle with that value at the bottom right.

Saved-text mode prefers cell paragraphs, including explicitly empty ones, then typed attributes.
Raw mode reverses that preference. Numeric attributes stay strings without floating-point
conversion. Dates, times, durations and booleans are not reformatted or localized. Formulas use
saved results whose freshness cannot be inferred. A formula lacking both saved representations
exports empty and produces `missing-formula-result`; an explicitly saved empty result is valid.
LibreOffice's namespace-qualified cached-error marker is an exception to raw attribute preference:
use saved error paragraphs, since its string attribute is normally empty for errors. An error
formula gets the missing-result warning when paragraphs are absent or their joined string is empty;
this does not validate error codes or whitespace-only representations. Error-cell attributes are
not fallback values; unusual representations are tracked in [issue
17](https://github.com/viell-dev/slop-ods2tsv/issues/17). Ordinary empty string results do not become
errors merely because their saved paragraphs resemble an error message.

Ordinary XML text whitespace follows ODF collapse rules; explicit `text:s`, `text:tab` and
`text:line-break` survive. Paragraphs join with LF. Annotations, drawings, nested tables and tracked
history, ruby annotations and footnote bodies do not contribute cell text. Ruby base text and note
citations remain. An ordinary space after an explicit whitespace element starts a new collapsible
run. All sheets remain in source document order, regardless of visibility; hidden rows and columns
also retain their data positions.

**Calc compatibility limit:** LibreOffice 25.2.3.2 can save literal spaces in rich-text/multi-line
cell paragraphs that Calc itself preserves when reopening the ODS. Strict ODF collapsing here can
remove paragraph-edge spaces or collapse interior runs, so extracted text can lose spaces visible
in Calc. Raw mode can have the same limit when no separate stored string is present. [Issue
16](https://github.com/viell-dev/slop-ods2tsv/issues/16) retains the evidence and future compatibility
decision; this alpha keeps the strict ODF policy rather than promise Calc's text interpretation.

## Manifest schema 1

`manifest.json` follows [manifest.schema.json](../manifest.schema.json). `manifest.txt` comes from
the same model and uses JSON-style escaping for names. It summarizes at most 20 merged ranges per
sheet; JSON retains the complete list within the documented limit.

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer 1, independent of executable version |
| `exporter` | Tool name and version from Cargo metadata |
| `source` | Basename, detected container (`ods`/`fods`), original file size in bytes |
| `exported_at` | UTC export time; intentionally varies between runs |
| `options` | Value mode, grid origin, rectangularity, merge fill and trimming rules |
| `tsv` | Encoding, BOM flag, delimiter, quoting and record terminator |
| `sheets` | Every original sheet, in workbook order |

Each sheet has one-based `position`, exact parsed `name`, relative `file`, exported `rows` and
`columns`, `merged_ranges` and `warnings`. Position agrees with array index. Filenames are cleaned
portable components: use the mapping rather than reversing sanitization. Warnings have `code`,
occurrence `count`, and readable `message`.

Merged ranges use **inclusive, one-based original coordinates**:

```json
{
  "start_row": 2,
  "start_column": 3,
  "end_row": 4,
  "end_column": 5
}
```

This represents C2:E4, anchored at C2. Empty merges and regions outside the trimmed TSV still
appear. Each logical region appears once, ordered by start row/column. Repeated source templates
expand into separate regions; exceeding 100,000 regions fails rather than truncating metadata.
Overlapping regions fail because their fill is ambiguous. Cell types, formulas, styles and
visibility are not otherwise archived, and the manifest cannot reconstruct the original workbook.
Merge fill uses only the anchor value. Stored alternate content in covered cells is discarded;
an empty anchor stays empty even if a covered cell contains content. Merge metadata retains
geometry, not those alternate values.

Ignore unknown additive fields. Incompatible meanings or removals require a new schema version.
Source paths exclude machine-specific absolute directories. TSV and filename output is
deterministic for identical input/options/environment; timestamps and automatic directories vary.

## Complete and partial exports

The tool exclusively creates a new directory and `.incomplete`, writes TSVs, consumes the complete
XML, flushes output, writes both manifests, then removes the marker last. Success is reported only
then. Ordinary failure removes owned files, never unrelated contents. Failed cleanup or interruption
can leave a marked partial directory. There is no resume/overwrite mode, and flushes do not promise
survival of power loss.
Failure to report the completed directory on stdout returns exit 1 and leaves the complete files
intact. This reporting failure does not roll back an otherwise successful export.
