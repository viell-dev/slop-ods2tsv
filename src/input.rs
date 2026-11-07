use crate::{Error, MAX_XML_BYTES, MAX_XML_DEPTH, Options, invalid, io, reader, sheet::Sheet};
use std::{
    fs::File,
    io::{BufRead, BufReader, Read},
    path::Path,
};
use xml::reader::{ParserConfig, XmlEvent};
use zip::ZipArchive;

enum Kind {
    Package(ZipArchive<BufReader<File>>),
    Flat(BufReader<File>),
}
pub(crate) struct Source {
    kind: Kind,
    size: u64,
}

fn spreadsheet_type(value: &str) -> bool {
    matches!(
        value.trim(),
        "application/vnd.oasis.opendocument.spreadsheet"
            | "application/vnd.oasis.opendocument.spreadsheet-template"
    )
}

impl Source {
    pub fn open(path: &Path) -> Result<Self, Error> {
        let file =
            File::open(path).map_err(|error| io(format!("opening {}", path.display()), error))?;
        let size = file
            .metadata()
            .map_err(|error| io("reading input metadata", error))?
            .len();
        let mut reader = BufReader::new(file);
        // Only route the stream; the selected reader supplies the actual format/syntax errors.
        let zip = reader
            .fill_buf()
            .map_err(|error| io("reading input", error))?
            .starts_with(b"PK");
        let kind = if zip {
            let mut archive = ZipArchive::new(reader)?;
            if let Some(bytes) = metadata(&mut archive, "mimetype", 1024)?
                && !spreadsheet_type(&String::from_utf8_lossy(&bytes))
            {
                return Err(invalid("package declares a non-spreadsheet document type"));
            }
            if let Some(manifest) = metadata(&mut archive, "META-INF/manifest.xml", 1024 * 1024)?
                && encrypted_content(&manifest)?
            {
                return Err(invalid(
                    "content.xml is encrypted; save an unencrypted copy before exporting",
                ));
            }
            Kind::Package(archive)
        } else {
            Kind::Flat(reader)
        };
        Ok(Self { kind, size })
    }

    pub fn format(&self) -> &'static str {
        match self.kind {
            Kind::Package(_) => "ods",
            Kind::Flat(_) => "fods",
        }
    }
    pub fn size(&self) -> u64 {
        self.size
    }

    pub fn read(
        &mut self,
        options: &Options,
        emit: impl FnMut(Sheet) -> Result<(), Error>,
    ) -> Result<(), Error> {
        match &mut self.kind {
            Kind::Package(archive) => {
                let content = archive.by_name("content.xml")?;
                reader::read(
                    BufReader::new(Limited {
                        inner: content,
                        remaining: MAX_XML_BYTES,
                    }),
                    options,
                    emit,
                )
            }
            Kind::Flat(file) => reader::read(
                Limited {
                    inner: file,
                    remaining: MAX_XML_BYTES,
                },
                options,
                emit,
            ),
        }
    }
}

fn metadata(
    archive: &mut ZipArchive<BufReader<File>>,
    name: &str,
    limit: u64,
) -> Result<Option<Vec<u8>>, Error> {
    match archive.by_name(name) {
        Ok(entry) => {
            let mut bytes = Vec::new();
            entry
                .take(limit + 1)
                .read_to_end(&mut bytes)
                .map_err(|error| io(format!("reading {name}"), error))?;
            if bytes.len() as u64 > limit {
                return Err(invalid(format!(
                    "package metadata {name} exceeds {limit} bytes"
                )));
            }
            Ok(Some(bytes))
        }
        Err(zip::result::ZipError::FileNotFound) => Ok(None),
        Err(error) => Err(error.into()),
    }
}

fn encrypted_content(bytes: &[u8]) -> Result<bool, Error> {
    const NS: &str = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0";
    let mut depth = 0usize;
    let mut entry = None;
    for event in ParserConfig::new()
        .max_data_length(1024 * 1024)
        .create_reader(bytes)
    {
        match event {
            Ok(XmlEvent::StartElement {
                name, attributes, ..
            }) => {
                depth += 1;
                if depth > MAX_XML_DEPTH {
                    return Err(invalid(format!(
                        "package manifest XML exceeds {MAX_XML_DEPTH} open elements"
                    )));
                }
                if name.namespace.as_deref() == Some(NS) {
                    if name.local_name == "file-entry"
                        && attributes.iter().any(|attribute| {
                            attribute.name.namespace.as_deref() == Some(NS)
                                && attribute.name.local_name == "full-path"
                                && attribute.value == "content.xml"
                        })
                    {
                        entry = Some(depth);
                    }
                    if name.local_name == "encryption-data" && entry.is_some() {
                        return Ok(true);
                    }
                }
            }
            Ok(XmlEvent::EndElement { .. }) => {
                if entry == Some(depth) {
                    entry = None;
                }
                depth = depth.saturating_sub(1);
            }
            Err(_) => return Ok(false), // Optional metadata is not a second workbook validity gate.
            _ => {}
        }
    }
    Ok(false)
}

struct Limited<R> {
    inner: R,
    remaining: u64,
}
impl<R: Read> Read for Limited<R> {
    fn read(&mut self, buffer: &mut [u8]) -> std::io::Result<usize> {
        if buffer.is_empty() {
            return Ok(0);
        }
        if self.remaining == 0 {
            return match self.inner.read(&mut [0])? {
                0 => Ok(0),
                _ => Err(std::io::Error::other(format!(
                    "content XML exceeds {MAX_XML_BYTES} bytes"
                ))),
            };
        }
        let length = buffer.len().min(self.remaining as usize);
        let read = self.inner.read(&mut buffer[..length])?;
        self.remaining -= read as u64;
        Ok(read)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn byte_limit_allows_exact_eof_and_rejects_additional_data() {
        let mut exact = Limited {
            inner: &b"abc"[..],
            remaining: 3,
        };
        let mut bytes = Vec::new();
        exact.read_to_end(&mut bytes).unwrap();
        assert_eq!(bytes, b"abc");
        let mut excessive = Limited {
            inner: &b"abcd"[..],
            remaining: 3,
        };
        assert!(excessive.read_to_end(&mut Vec::new()).is_err());
    }

    #[test]
    fn read_budget_errors_keep_their_cause_without_an_xml_position() {
        let error = reader::read(
            Limited {
                inner: &b"<document/>"[..],
                remaining: 3,
            },
            &Options::default(),
            |_| Ok(()),
        )
        .unwrap_err();
        assert!(matches!(error, Error::Read { .. }));
        assert_eq!(
            error.to_string(),
            format!("cannot read workbook content: content XML exceeds {MAX_XML_BYTES} bytes")
        );
        assert!(std::error::Error::source(&error).is_some());
    }
}
