use crate::{
    Error, Export, MAX_OUTPUT_BYTES, Manifest, Options, SheetManifest, invalid, io,
    manifest::{Dialect, Exporter, Settings, Source},
    sheet::Sheet,
};
use std::{
    collections::{HashMap, HashSet},
    fs::{self, File, OpenOptions},
    io::{BufWriter, Write},
    path::{Path, PathBuf},
};

pub(crate) struct Run {
    directory: PathBuf,
    owned: Vec<PathBuf>,
    names: HashSet<String>,
    suffixes: HashMap<String, usize>,
    sheets: Vec<SheetManifest>,
    remaining: u64,
}

struct LimitedWriter<'a, W> {
    inner: W,
    remaining: &'a mut u64,
}

impl<W: Write> Write for LimitedWriter<'_, W> {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        if bytes.len() as u64 > *self.remaining {
            return Err(std::io::Error::other(format!(
                "export exceeds {MAX_OUTPUT_BYTES} total TSV/manifest bytes"
            )));
        }
        let written = self.inner.write(bytes)?;
        *self.remaining -= written as u64;
        Ok(written)
    }

    fn flush(&mut self) -> std::io::Result<()> {
        self.inner.flush()
    }
}

fn safe_name(name: &str) -> String {
    let mut cleaned = String::new();
    let mut units = 0;
    for ch in name.chars() {
        let ch = if ch.is_control() || "<>:\"/\\|?*".contains(ch) {
            '_'
        } else {
            ch
        };
        if units + ch.len_utf16() > 80 {
            break;
        }
        units += ch.len_utf16();
        cleaned.push(ch);
    }
    let trimmed = cleaned.trim_matches([' ', '.']);
    let mut result = if trimmed.is_empty() {
        "Sheet".into()
    } else {
        trimmed.to_owned()
    };
    let stem = result
        .split('.')
        .next()
        .unwrap_or("")
        .trim_end()
        .to_uppercase();
    if matches!(
        stem.as_str(),
        "CON" | "PRN" | "AUX" | "NUL" | "CONIN$" | "CONOUT$"
    ) || ["COM", "LPT"].iter().any(|prefix| {
        stem.strip_prefix(prefix).is_some_and(|suffix| {
            matches!(
                suffix,
                "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "¹" | "²" | "³"
            )
        })
    }) {
        result.insert(0, '_');
    }
    result
}

impl Run {
    pub fn new(input: &Path, options: &Options) -> Result<Self, Error> {
        let directory = if let Some(path) = &options.output {
            fs::create_dir(path).map_err(|error| {
                io(
                    format!("creating new output directory {}", path.display()),
                    error,
                )
            })?;
            path.clone()
        } else {
            let stem = safe_name(&input.file_stem().unwrap_or_default().to_string_lossy());
            let base = format!(
                "{stem} - {}",
                jiff::Zoned::now().strftime("%Y-%m-%dT%H-%M-%S")
            );
            let mut claimed = None;
            for attempt in 1..=usize::MAX {
                let path = PathBuf::from(if attempt == 1 {
                    base.clone()
                } else {
                    format!("{base} ({attempt})")
                });
                match fs::create_dir(&path) {
                    Ok(()) => {
                        claimed = Some(path);
                        break;
                    }
                    Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {}
                    Err(error) => return Err(io("creating output directory", error)),
                }
            }
            claimed.ok_or_else(|| invalid("could not claim a fresh output directory"))?
        };
        let mut run = Self {
            directory,
            owned: vec![],
            names: HashSet::new(),
            suffixes: HashMap::new(),
            sheets: vec![],
            remaining: MAX_OUTPUT_BYTES,
        };
        if let Err(error) = run.file(".incomplete").and_then(|mut file| {
            file.write_all(b"Incomplete ODS2TSV export. Do not consume this directory.\n")
                .map_err(|error| io("writing incomplete marker", error))
        }) {
            return Err(run.abort(error));
        }
        Ok(run)
    }

    fn file(&mut self, name: &str) -> Result<File, Error> {
        let path = self.directory.join(name);
        let file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&path)
            .map_err(|error| io(format!("creating {}", path.display()), error))?;
        self.owned.push(path);
        Ok(file)
    }

    pub fn write(&mut self, sheet: Sheet) -> Result<(), Error> {
        let base = safe_name(&sheet.name);
        let (file, output) = loop {
            let next = self.suffixes.entry(base.to_lowercase()).or_insert(1);
            let attempt = *next;
            *next = next
                .checked_add(1)
                .ok_or_else(|| invalid("filename suffix overflow"))?;
            let name = if attempt == 1 {
                format!("{base}.tsv")
            } else {
                format!("{base} ({attempt}).tsv")
            };
            if !self.names.insert(name.to_lowercase()) {
                continue;
            }
            match self.file(&name) {
                Ok(file) => {
                    break (name, file);
                }
                Err(Error::Io { source, .. })
                    if source.kind() == std::io::ErrorKind::AlreadyExists =>
                {
                    continue;
                }
                Err(error) => return Err(error),
            }
        };
        let written = sheet.write(BufWriter::new(LimitedWriter {
            inner: output,
            remaining: &mut self.remaining,
        }))?;
        self.sheets.push(SheetManifest {
            position: self.sheets.len() + 1,
            name: sheet.name,
            file,
            rows: written.rows,
            columns: written.columns,
            merged_ranges: written.ranges,
            warnings: written.warnings,
        });
        Ok(())
    }

    pub fn finish(
        &mut self,
        format: &str,
        size: u64,
        path: &Path,
        options: &Options,
    ) -> Result<Export, Error> {
        let manifest = Manifest {
            schema_version: 1,
            exporter: Exporter {
                name: "ods2tsv".into(),
                version: env!("CARGO_PKG_VERSION").into(),
            },
            source: Source {
                name: path
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .into(),
                format: format.into(),
                size_bytes: size,
            },
            exported_at: jiff::Timestamp::now().to_string(),
            options: Settings {
                value_mode: options.values.label().into(),
                preserve_whitespace: options.preserve_whitespace,
                grid_origin: "A1".into(),
                rectangular: true,
                merged_cells: "fill".into(),
                trim: "trailing-empty-rows-and-columns".into(),
            },
            tsv: Dialect {
                encoding: "utf-8".into(),
                bom: false,
                delimiter: "\t".into(),
                quote: "\"".into(),
                doublequote: true,
                record_terminator: "\r\n".into(),
            },
            sheets: std::mem::take(&mut self.sheets),
        };
        let mut json = BufWriter::new(LimitedWriter {
            inner: self.file("manifest.json")?,
            remaining: &mut self.remaining,
        });
        serde_json::to_writer_pretty(&mut json, &manifest)?;
        json.write_all(b"\n")
            .map_err(|error| io("writing JSON manifest", error))?;
        json.flush()
            .map_err(|error| io("flushing JSON manifest", error))?;
        drop(json);
        let mut text = BufWriter::new(LimitedWriter {
            inner: self.file("manifest.txt")?,
            remaining: &mut self.remaining,
        });
        text.write_all(manifest.text().as_bytes())
            .map_err(|error| io("writing text manifest", error))?;
        text.flush()
            .map_err(|error| io("flushing text manifest", error))?;
        fs::remove_file(self.directory.join(".incomplete"))
            .map_err(|error| io("completing export", error))?;
        Ok(Export {
            directory: self.directory.clone(),
            manifest,
        })
    }

    pub fn abort(&mut self, error: Error) -> Error {
        let marker = self.directory.join(".incomplete");
        let mut failed = false;
        for file in self.owned.iter().rev().filter(|file| **file != marker) {
            if fs::remove_file(file).is_err() {
                failed = true;
            }
        }
        if !failed {
            if self.owned.contains(&marker) && fs::remove_file(&marker).is_err() {
                failed = true;
            }
            if !failed && fs::remove_dir(&self.directory).is_err() {
                failed = true;
                // Another file may have appeared: retain the completion marker without touching it.
                let _ = OpenOptions::new()
                    .write(true)
                    .create_new(true)
                    .open(&marker);
            }
        }
        if failed {
            invalid(format!(
                "{error}; cleanup incomplete: inspect marked partial export {}",
                self.directory.display()
            ))
        } else {
            error
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sheet::{Cell, Row};

    #[test]
    fn output_byte_counter_is_shared_exact_and_counts_encoded_bytes() {
        let mut remaining = 5;
        let mut bytes = Vec::new();
        let mut writer = LimitedWriter {
            inner: &mut bytes,
            remaining: &mut remaining,
        };
        writer.write_all("é".as_bytes()).unwrap();
        writer.write_all(b"abc").unwrap();
        assert!(
            writer
                .write_all(b"x")
                .unwrap_err()
                .to_string()
                .contains("total TSV/manifest bytes")
        );
        assert_eq!(bytes, "éabc".as_bytes());
        assert_eq!(remaining, 0);
    }

    #[test]
    fn output_budget_covers_multiple_sheets_and_manifests_with_cleanup() {
        fn sheet() -> Sheet {
            Sheet {
                name: "Budget".into(),
                rows: vec![Row {
                    start: 0,
                    repeat: 1,
                    cells: vec![Cell {
                        column: 0,
                        repeat: 1,
                        row_span: 1,
                        column_span: 1,
                        value: "\"".into(),
                        missing_formula: false,
                    }],
                }],
            }
        }
        // A single quoted quote encodes as four quote bytes plus CRLF, not one value byte.
        let reference = tempfile::tempdir().unwrap();
        let options = Options {
            output: Some(reference.path().join("out")),
            ..Options::default()
        };
        let mut run = Run::new(Path::new("source.ods"), &options).unwrap();
        run.write(sheet()).unwrap();
        run.write(sheet()).unwrap();
        let complete = run
            .finish("ods", 0, Path::new("source.ods"), &options)
            .unwrap();
        let json_bytes = fs::metadata(complete.directory.join("manifest.json"))
            .unwrap()
            .len();
        // Allow timestamp precision to vary by a few bytes; 64 bytes cannot fit the text manifest.
        for (budget, phase) in [
            (11, "second sheet"),
            (12, "JSON manifest"),
            (12 + json_bytes + 64, "text manifest"),
        ] {
            let parent = tempfile::tempdir().unwrap();
            let options = Options {
                output: Some(parent.path().join("out")),
                ..Options::default()
            };
            let mut run = Run::new(Path::new("source.ods"), &options).unwrap();
            run.remaining = budget;
            run.write(sheet()).unwrap();
            let result = run.write(sheet());
            let error = if phase == "second sheet" {
                result.unwrap_err()
            } else {
                result.unwrap();
                run.finish("ods", 0, Path::new("source.ods"), &options)
                    .unwrap_err()
            };
            if phase == "text manifest" {
                assert!(
                    fs::metadata(run.directory.join("manifest.json"))
                        .unwrap()
                        .len()
                        > 0
                );
                assert!(run.directory.join("manifest.txt").exists());
            }
            assert!(
                error.to_string().contains("total TSV/manifest bytes"),
                "{error}"
            );
            let error = run.abort(error);
            assert!(!options.output.as_ref().unwrap().exists(), "{error}");
        }
    }
    #[test]
    fn portable_names_handle_windows_devices_and_unicode() {
        for name in ["CON", "NUL.txt", "COM¹", "lpt9", "CONIN$"] {
            assert!(safe_name(name).starts_with('_'));
        }
        assert_eq!(safe_name("  A/B. "), "A_B");
        assert_eq!(safe_name(". ."), "Sheet");
        assert_eq!(safe_name("🦀 café"), "🦀 café");
        assert!(safe_name(&"🦀".repeat(100)).encode_utf16().count() <= 80);
    }

    #[test]
    fn cleanup_preserves_unrelated_contents_and_leaves_marker() {
        let parent = tempfile::tempdir().unwrap();
        let destination = parent.path().join("out");
        let mut run = Run::new(
            Path::new("input.ods"),
            &Options {
                output: Some(destination.clone()),
                ..Options::default()
            },
        )
        .unwrap();
        drop(run.file("owned.tsv").unwrap());
        fs::write(destination.join("unrelated"), b"keep").unwrap();
        let error = run.abort(invalid("synthetic failure"));
        assert!(error.to_string().contains("cleanup incomplete"));
        assert_eq!(fs::read(destination.join("unrelated")).unwrap(), b"keep");
        assert!(!destination.join("owned.tsv").exists());
        assert!(destination.join(".incomplete").exists());
    }
}
