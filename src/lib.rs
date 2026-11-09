//! Saved-value extraction for ODS and FODS.
//!
//! The supported product is the portable CLI and its documented TSV/manifest contract. This
//! source-level Rust API supports that implementation and its tests; it has no separate stability
//! promise, even when the CLI release is stable. It can change between releases.
//!
//! [`export`] creates a complete export in a new directory. [`Options::default`] uses saved cell
//! text with ODF whitespace collapsing and a timestamped destination. No mode calculates formulas.
#![warn(missing_docs)]
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
    /// Saved paragraph or stored-attribute preference; defaults to [`ValueMode::SavedText`].
    pub values: ValueMode,
    /// Keep literal whitespace inside cell paragraphs instead of applying ODF collapsing.
    pub preserve_whitespace: bool,
}

/// A complete export and its metadata. Only returned after the incomplete marker is removed.
#[derive(Debug)]
pub struct Export {
    /// Created output directory, relative or absolute as selected by the caller/default.
    pub directory: PathBuf,
    /// Ordered workbook metadata also written to `manifest.json`.
    pub manifest: Manifest,
}

/// Input, validation or output failure. Messages are diagnostics, not a stable machine interface.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// Filesystem or stream failure outside XML reading/decoding.
    #[error("{context}: {source}")]
    Io {
        /// Operation and relevant path, when available.
        context: String,
        /// Underlying operating-system error.
        source: std::io::Error,
    },
    /// ODS container access, ZIP integrity or compression failure.
    #[error("cannot read ODF package: {0}")]
    Zip(#[from] zip::result::ZipError),
    /// Malformed XML, retaining the parser's position when available.
    #[error("invalid workbook XML: {0}")]
    Xml(#[source] xml::reader::Error),
    /// Content stream I/O failure, including decompression and content-byte limits.
    #[error("cannot read workbook content: {message}")]
    Read {
        /// Read diagnostic without a potentially misleading XML position.
        message: String,
        /// Original parser/reader error for inspection.
        #[source]
        source: xml::reader::Error,
    },
    /// Character decoding failure; a position may be unavailable.
    #[error("cannot decode workbook XML: {message}")]
    Decode {
        /// Decoding diagnostic.
        message: String,
        /// Original parser/decoder error for inspection.
        #[source]
        source: xml::reader::Error,
    },
    /// TSV encoding or writing failure.
    #[error("cannot write TSV: {0}")]
    Csv(#[from] csv::Error),
    /// JSON manifest encoding or writing failure.
    #[error("cannot write manifest: {0}")]
    Json(#[from] serde_json::Error),
    /// Unsupported/invalid workbook structure, destination or exceeded resource limit.
    #[error("{0}")]
    Invalid(String),
}

impl From<xml::reader::Error> for Error {
    fn from(source: xml::reader::Error) -> Self {
        match source.kind() {
            xml::reader::ErrorKind::Io(error) => Self::Read {
                message: error.to_string(),
                source,
            },
            xml::reader::ErrorKind::Utf8(error) => Self::Decode {
                message: error.to_string(),
                source,
            },
            xml::reader::ErrorKind::UnexpectedEof => Self::Decode {
                message: "unexpected end of input while decoding XML".into(),
                source,
            },
            _ => Self::Xml(source),
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
///
/// The input is detected by content and left unchanged. The destination parent must exist and be
/// writable. Success means both manifests are written and `.incomplete` is removed; it does not
/// promise durability across power loss. An interrupted process can leave a marked partial export.
///
/// # Errors
///
/// Returns [`Error`] for unreadable/encrypted/malformed input, unsupported geometry, exceeded
/// limits, an existing destination, or output failures. No partial metadata is returned on error.
pub fn export(path: &Path, options: &Options) -> Result<Export, Error> {
    let mut source = input::Source::open(path)?;
    let mut run = output::Run::new(path, options)?;
    let result = source.read(options, |sheet| run.write(sheet));
    match result.and_then(|()| run.finish(source.format(), source.size(), path, options)) {
        Ok(export) => Ok(export),
        Err(error) => Err(run.abort(error)),
    }
}
