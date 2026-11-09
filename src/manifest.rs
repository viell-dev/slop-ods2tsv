use serde::{Deserialize, Serialize};

/// Inclusive one-based coordinates in the original workbook, independent of TSV trimming.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MergedRange {
    /// First original row, one-based and inclusive.
    pub start_row: usize,
    /// First original column, one-based and inclusive.
    pub start_column: usize,
    /// Last original row, one-based and inclusive.
    pub end_row: usize,
    /// Last original column, one-based and inclusive.
    pub end_column: usize,
}

/// One warning category aggregated over logical occurrences in a sheet.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Warning {
    /// Machine-readable warning category, such as `missing-formula-result`.
    pub code: String,
    /// Logical occurrences in this sheet, including repeated cells/rows.
    pub count: usize,
    /// Human-readable explanation; consumers should classify by `code`.
    pub message: String,
}

/// One sheet in workbook order and its trimmed output dimensions.
#[derive(Debug, Serialize, Deserialize)]
pub struct SheetManifest {
    /// One-based position in the original workbook, matching array order.
    pub position: usize,
    /// Original parsed sheet name, without filename sanitization.
    pub name: String,
    /// Unique portable TSV filename relative to the export directory.
    pub file: String,
    /// Exported rectangular height in records; zero for an empty sheet.
    pub rows: usize,
    /// Exported rectangular width in fields; zero for an empty sheet.
    pub columns: usize,
    /// All original merged regions, including empty/outlying regions, in start-coordinate order.
    pub merged_ranges: Vec<MergedRange>,
    /// Aggregated warning categories and occurrence counts for this sheet.
    pub warnings: Vec<Warning>,
}

/// Schema-1 workbook metadata. Unknown additive JSON fields may be ignored.
#[derive(Debug, Serialize, Deserialize)]
pub struct Manifest {
    /// Release-pinned schema selector; absent in exports before alpha.5.
    #[serde(rename = "$schema", default, skip_serializing_if = "Option::is_none")]
    pub schema: Option<String>,
    /// Format compatibility version (currently 1), independent of exporter version.
    pub schema_version: u32,
    /// Executable identity from Cargo metadata.
    pub exporter: Exporter,
    /// Input basename, detected format and original byte size.
    pub source: Source,
    /// UTC export timestamp as an RFC 3339 string; varies between runs.
    pub exported_at: String,
    /// Effective value, whitespace and geometry policies.
    pub options: Settings,
    /// Encoding and quoting dialect shared by every sheet TSV.
    pub tsv: Dialect,
    /// Every sheet in original workbook order, including hidden and empty sheets.
    pub sheets: Vec<SheetManifest>,
}

/// Identity of the executable that produced an export.
#[derive(Debug, Serialize, Deserialize)]
pub struct Exporter {
    /// Tool name (`ods2tsv`).
    pub name: String,
    /// Executable SemVer version, distinct from the manifest schema version.
    pub version: String,
}
/// Input identity without its private absolute path.
#[derive(Debug, Serialize, Deserialize)]
pub struct Source {
    /// Input basename, excluding machine-specific parent directories.
    pub name: String,
    /// Content-detected container: `ods` or `fods`.
    pub format: String,
    /// Original input file size in bytes, before decompression.
    pub size_bytes: u64,
}
/// Effective extraction policies recorded for reproducibility.
#[derive(Debug, Serialize, Deserialize)]
pub struct Settings {
    /// Effective preference: `saved-text` or `raw`.
    pub value_mode: String,
    /// Absent in manifests written before alpha.3; those used ODF collapsing.
    #[serde(default)]
    pub preserve_whitespace: bool,
    /// Original coordinate origin (`A1`).
    pub grid_origin: String,
    /// Whether all records share the final sheet width (always true).
    pub rectangular: bool,
    /// Anchor-value fill policy (`fill`).
    pub merged_cells: String,
    /// Omitted empty extent policy (`trailing-empty-rows-and-columns`).
    pub trim: String,
}
/// TSV text/quoting settings; these do not restore workbook types or styles.
#[derive(Debug, Serialize, Deserialize)]
pub struct Dialect {
    /// Text encoding (`UTF-8`).
    pub encoding: String,
    /// Whether a byte-order mark is emitted (false).
    pub bom: bool,
    /// Field separator, a tab character.
    pub delimiter: String,
    /// Quoting delimiter, a double quote.
    pub quote: String,
    /// Whether embedded quotes are doubled (true).
    pub doublequote: bool,
    /// Record ending, CRLF; embedded field line breaks remain field content.
    pub record_terminator: String,
}

impl Manifest {
    pub(crate) fn text(&self) -> String {
        let mut text = format!(
            "Workbook: {}\nExporter: {} {}\nExported at: {}\nValues: {}\nParagraph whitespace: {}\n\
             Formulas are not recalculated.\n\
             Grid: original A1 origin; rectangular; merged values filled; trailing emptiness omitted\n\
             TSV: UTF-8, tabs, double-quote escaping, CRLF records\n\nSheets in original workbook order:\n",
            serde_json::to_string(&self.source.name).expect("strings serialize"),
            self.exporter.name,
            self.exporter.version,
            self.exported_at,
            self.options.value_mode,
            if self.options.preserve_whitespace {
                "preserved"
            } else {
                "ODF collapse"
            },
        );
        for sheet in &self.sheets {
            text.push_str(&format!(
                "{}. {} -> {}\n",
                sheet.position,
                serde_json::to_string(&sheet.name).expect("strings serialize"),
                serde_json::to_string(&sheet.file).expect("strings serialize"),
            ));
        }
        text.push_str("\nMachine-readable details: manifest.json\n");
        text
    }
}
