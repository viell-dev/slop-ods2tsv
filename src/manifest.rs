use serde::{Deserialize, Serialize};

/// Inclusive one-based coordinates in the original workbook, independent of TSV trimming.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MergedRange {
    pub start_row: usize,
    pub start_column: usize,
    pub end_row: usize,
    pub end_column: usize,
}

impl MergedRange {
    pub(crate) fn label(&self) -> String {
        fn column(mut number: usize) -> String {
            let mut chars = Vec::new();
            while number > 0 {
                number -= 1;
                chars.push((b'A' + (number % 26) as u8) as char);
                number /= 26;
            }
            chars.iter().rev().collect()
        }
        format!(
            "{}{}:{}{}",
            column(self.start_column),
            self.start_row,
            column(self.end_column),
            self.end_row
        )
    }
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
            "Workbook: {}\nExporter: {} {}\nExported at: {}\nValues: {}\n\
             Formulas are not recalculated.\n\
             Grid: original A1 origin; rectangular; merged values filled; trailing emptiness omitted\n\
             TSV: UTF-8, tabs, double-quote escaping, CRLF records\n\nSheets in original workbook order:\n",
            serde_json::to_string(&self.source.name).expect("strings serialize"),
            self.exporter.name,
            self.exporter.version,
            self.exported_at,
            self.options.value_mode,
        );
        for sheet in &self.sheets {
            text.push_str(&format!(
                "{}. {} -> {} ({} rows, {} columns)\n",
                sheet.position,
                serde_json::to_string(&sheet.name).expect("strings serialize"),
                serde_json::to_string(&sheet.file).expect("strings serialize"),
                sheet.rows,
                sheet.columns
            ));
            if !sheet.merged_ranges.is_empty() {
                text.push_str("   Merged ranges in original coordinates: ");
                let labels: Vec<_> = sheet
                    .merged_ranges
                    .iter()
                    .take(20)
                    .map(MergedRange::label)
                    .collect();
                text.push_str(&labels.join(", "));
                if sheet.merged_ranges.len() > 20 {
                    text.push_str(" (complete list in manifest.json)");
                }
                text.push('\n');
            }
            for warning in &sheet.warnings {
                text.push_str(&format!(
                    "   Warning [{}] ({}): {}\n",
                    warning.code, warning.count, warning.message
                ));
            }
        }
        text.push_str("\nMachine-readable details: manifest.json\n");
        text
    }
}
