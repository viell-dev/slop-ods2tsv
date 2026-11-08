use serde::{Deserialize, Serialize};

/// Inclusive one-based coordinates in the original workbook, independent of TSV trimming.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MergedRange {
    pub start_row: usize,
    pub start_column: usize,
    pub end_row: usize,
    pub end_column: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Warning {
    pub code: String,
    pub count: usize,
    pub message: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SheetManifest {
    pub position: usize,
    pub name: String,
    pub file: String,
    pub rows: usize,
    pub columns: usize,
    pub merged_ranges: Vec<MergedRange>,
    pub warnings: Vec<Warning>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Manifest {
    /// Release-pinned schema selector; absent in exports before alpha.5.
    #[serde(rename = "$schema", default, skip_serializing_if = "Option::is_none")]
    pub schema: Option<String>,
    pub schema_version: u32,
    pub exporter: Exporter,
    pub source: Source,
    pub exported_at: String,
    pub options: Settings,
    pub tsv: Dialect,
    pub sheets: Vec<SheetManifest>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Exporter {
    pub name: String,
    pub version: String,
}
#[derive(Debug, Serialize, Deserialize)]
pub struct Source {
    pub name: String,
    pub format: String,
    pub size_bytes: u64,
}
#[derive(Debug, Serialize, Deserialize)]
pub struct Settings {
    pub value_mode: String,
    /// Absent in manifests written before alpha.3; those used ODF collapsing.
    #[serde(default)]
    pub preserve_whitespace: bool,
    pub grid_origin: String,
    pub rectangular: bool,
    pub merged_cells: String,
    pub trim: String,
}
#[derive(Debug, Serialize, Deserialize)]
pub struct Dialect {
    pub encoding: String,
    pub bom: bool,
    pub delimiter: String,
    pub quote: String,
    pub doublequote: bool,
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
