//! Saved-value extraction for ODS and FODS. The alpha API is not yet stable.
mod input;
mod manifest;
mod output;
mod reader;
mod sheet;

use std::path::{Path, PathBuf};

pub use manifest::{Manifest, MergedRange, SheetManifest, Warning};
pub use reader::ValueMode;

/// Maximum logical fields in one rectangular exported sheet.
pub const MAX_CELLS: usize = 10_000_000;
/// Maximum bytes read from a workbook's decompressed content XML.
pub const MAX_XML_BYTES: u64 = 64 * 1024 * 1024;
/// Maximum separate merged regions retained for one sheet.
pub const MAX_MERGES: usize = 100_000;
/// Maximum bytes in one extracted cell.
pub const MAX_CELL_BYTES: usize = 1024 * 1024;
/// Maximum combined bytes written to TSV files and both manifests in one export.
pub const MAX_OUTPUT_BYTES: u64 = 256 * 1024 * 1024;
/// Maximum open XML elements, including ignored subtrees and package metadata.
pub const MAX_XML_DEPTH: usize = 256;

/// User-selectable export settings.
#[derive(Debug, Default, Clone)]
pub struct Options {
    /// An explicit new destination, or a fresh timestamped directory in the current directory.
    pub output: Option<PathBuf>,
    pub values: ValueMode,
    /// Keep literal whitespace inside cell paragraphs instead of applying ODF collapsing.
    pub preserve_whitespace: bool,
}

/// A complete export and its metadata. Only returned after the incomplete marker is removed.
#[derive(Debug)]
pub struct Export {
    pub directory: PathBuf,
    pub manifest: Manifest,
}

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("{context}: {source}")]
    Io {
        context: String,
        source: std::io::Error,
    },
    #[error("cannot read ODF package: {0}")]
    Zip(#[from] zip::result::ZipError),
    #[error("invalid workbook XML: {0}")]
    Xml(#[source] xml::reader::Error),
    #[error("cannot read workbook content: {message}")]
    Read {
        message: String,
        #[source]
        source: xml::reader::Error,
    },
    #[error("cannot write TSV: {0}")]
    Csv(#[from] csv::Error),
    #[error("cannot write manifest: {0}")]
    Json(#[from] serde_json::Error),
    #[error("{0}")]
    Invalid(String),
}

impl From<xml::reader::Error> for Error {
    fn from(source: xml::reader::Error) -> Self {
        if let xml::reader::ErrorKind::Io(error) = source.kind() {
            Self::Read {
                message: error.to_string(),
                source,
            }
        } else {
            Self::Xml(source)
        }
    }
}

pub(crate) fn io(context: impl Into<String>, source: std::io::Error) -> Error {
    Error::Io {
        context: context.into(),
        source,
    }
}

pub(crate) fn invalid(message: impl Into<String>) -> Error {
    Error::Invalid(message.into())
}

/// Export every sheet without recalculating formulas or modifying the input.
///
/// Failures clean up only files created by this run. If cleanup cannot complete, the error names
/// the marked partial directory. Existing destinations are never reused.
pub fn export(path: &Path, options: &Options) -> Result<Export, Error> {
    let mut source = input::Source::open(path)?;
    let mut run = output::Run::new(path, options)?;
    let result = source.read(options, |sheet| run.write(sheet));
    match result.and_then(|()| run.finish(source.format(), source.size(), path, options)) {
        Ok(export) => Ok(export),
        Err(error) => Err(run.abort(error)),
    }
}
