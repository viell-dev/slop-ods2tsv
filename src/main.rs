use clap::Parser;
use ods2tsv::{Options, ValueMode};
use std::{
    io::{self, Write},
    path::PathBuf,
    process::ExitCode,
};

/// Export saved ODS/FODS sheet values to TSV with ordered workbook manifests.
#[derive(Parser)]
#[command(
    name = "ods2tsv",
    bin_name = "ods2tsv",
    version,
    term_width = 100,
    after_help = "Exports every sheet, including hidden and empty sheets. Preserves original coordinates and fills merged cells. Formulas use saved results; they are never recalculated.\n\nOutput: one TSV per sheet, manifest.txt, and manifest.json (including original merged ranges). The destination must be new. Without --output, creates a fresh timestamped directory in the current working directory.\n\nLimits: 64 MiB content XML, 256 open XML elements, 256 MiB total TSV/manifest bytes, 10,000,000 rectangular fields per sheet, 1 MiB per cell, 100,000 merged regions per sheet. Encrypted workbook content is unsupported."
)]
struct Args {
    /// Input OpenDocument spreadsheet (ZIP package or flat XML, detected by content)
    file: PathBuf,
    /// Prefer stored values (unlocalized numbers, ISO dates) over saved paragraph text
    #[arg(short, long)]
    raw: bool,
    /// Keep literal paragraph whitespace (useful for Calc rich-text and multi-line cells)
    #[arg(long)]
    preserve_whitespace: bool,
    /// Create this new output directory instead of a timestamped directory
    #[arg(short, long, value_name = "DIR")]
    output: Option<PathBuf>,
}

fn main() -> ExitCode {
    let args = Args::parse();
    let options = Options {
        output: args.output,
        preserve_whitespace: args.preserve_whitespace,
        values: if args.raw {
            ValueMode::Raw
        } else {
            ValueMode::SavedText
        },
    };
    match ods2tsv::export(&args.file, &options) {
        Ok(export) => {
            for sheet in &export.manifest.sheets {
                for warning in &sheet.warnings {
                    let _ = writeln!(
                        io::stderr().lock(),
                        "warning: {:?}: {} ({})",
                        sheet.name,
                        warning.message,
                        warning.count
                    );
                }
            }
            let _ = writeln!(
                io::stderr().lock(),
                "Exported {} sheets.",
                export.manifest.sheets.len()
            );
            if let Err(error) = writeln!(io::stdout().lock(), "{}", export.directory.display()) {
                let _ = writeln!(
                    io::stderr().lock(),
                    "error: export completed at {}, but its path could not be written to stdout: {error}",
                    export.directory.display()
                );
                return ExitCode::FAILURE;
            }
            ExitCode::SUCCESS
        }
        Err(error) => {
            let _ = writeln!(
                io::stderr().lock(),
                "error: {}: {error}",
                args.file.display()
            );
            ExitCode::FAILURE
        }
    }
}
