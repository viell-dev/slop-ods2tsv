# Export format

This describes the `0.1.0-beta.1` source and manifest schema 1; GitHub releases determine which
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
use saved error paragraphs containing a non-whitespace character, since the string attribute is
normally empty for errors. Otherwise fall back to a typed attribute containing a non-whitespace
character. If neither exists, export empty and warn for formulas, including when empty paragraphs
only contribute separators. The selected representation keeps its spaces; error codes are not
validated or translated. Ordinary empty string results remain valid and do not become errors
merely because their saved paragraphs resemble an error message.

By default, ordinary XML text whitespace follows ODF collapse rules; explicit `text:s`, `text:tab`
and `text:line-break` survive. Paragraphs join with LF. Annotations, drawings, nested tables and tracked
history, ruby annotations and footnote bodies do not contribute cell text. Ruby base text and note
citations remain. An ordinary space after an explicit whitespace element starts a new collapsible
run. All sheets remain in source document order, regardless of visibility; hidden rows and columns
also retain their data positions.

`--preserve-whitespace` keeps literal character data inside these cell paragraphs after normal XML
decoding, including leading/trailing spaces, runs, tabs and line breaks. Explicit whitespace and
paragraph separators still apply. It does not preserve indentation outside paragraphs or text in
ignored subtrees. XML's own line-ending and attribute normalization still applies. Saved/raw value
preference is unchanged, so raw attributes can take priority over the paragraphs in raw mode.

Examples below show decoded cell values, with quotes marking boundaries and `\n` a line break:

| Cell paragraphs | Default | Preserved |
| --- | --- | --- |
| `<text:p>  A  B </text:p>` | `"A B"` | `"  A  B "` |
| `<text:p>A</text:p><text:p>  B</text:p>` | `"A\nB"` | `"A\n  B"` |
| `<text:p>A<text:s/>B</text:p>` | `"A B"` | `"A B"` |
| `<text:p>A<text:s/></text:p>` | `"A "` | `"A "` |

Explicit ODF spaces survive both policies, including trailing spaces. The preservation option does
not add blanket trimming or remove explicit whitespace. TSV quoting is applied after these values
are selected; the explanatory quotes above are not a promise of quotes around every TSV field.

LibreOffice 25.2.3.2 saves some rich-text/multi-line spaces literally, which Calc preserves on
reopening. The option retains those spaces in the real-application tests; the default can still
collapse them. Use the option for that compatibility requirement. It is explicit because literal
preservation can also retain indentation inside pretty-printed XML paragraphs, and producer
identity alone does not establish text semantics. This is not a promise of full Calc rendering or
every producer/version. [Issue 16](https://github.com/viell-dev/slop-ods2tsv/issues/16) records the
evidence and alternatives.

## Manifest schema 1

`manifest.json` follows [manifest.schema.json](../manifest.schema.json). From alpha.5 it includes
`$schema` pointing to that schema at the exporter's release tag, matching the schema document's
`$id`. The selector is optional for backward compatibility with earlier schema-1 exports. A new
release may add fields without changing schema 1; consumers should ignore unknown additive fields.

`README.txt` is the human overview, named `manifest.txt` before alpha.5. It comes from the same
model and uses JSON-style escaping for names. It contains the workbook/settings header and the
sheet-name-to-filename map in original order. Dimensions, merge details and warnings are JSON-only;
the CLI also reports warnings to stderr.

| Field | Meaning |
| --- | --- |
| `$schema` | Release-pinned JSON Schema URI, present from alpha.5 |
| `schema_version` | Integer 1, independent of executable version |
| `exporter` | Tool name and version from Cargo metadata |
| `source` | Basename, detected container (`ods`/`fods`), original file size in bytes |
| `exported_at` | UTC export time; intentionally varies between runs |
| `options` | Value mode, paragraph whitespace, grid origin, rectangularity, merge fill and trimming rules |
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
`options.preserve_whitespace` is an additive boolean from alpha.3; absent means `false`, the ODF
collapse used by earlier exports. The text manifest names the same paragraph whitespace policy.
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

Read, decompression, checksum and content-byte-limit failures report a workbook read error. XML
syntax errors retain the parser's line/column. Character-decoding failures omit a position when
the decoder cannot supply one. Input is parsed once; these diagnostics do not add a separate
pre-validation pass. Resource limits and cleanup also apply to ignored XML and output
expansion; see [the README](../README.md#scope-and-limits) for the fixed caps.
