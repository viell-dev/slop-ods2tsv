use crate::{
    Error, Export, Manifest, Options, SheetManifest, invalid, io,
    manifest::{Dialect, Exporter, Settings, Source},
    sheet::Sheet,
};
use std::{
    collections::HashSet,
    fs::{self, File, OpenOptions},
    io::{BufWriter, Write},
    path::{Path, PathBuf},
};

pub(crate) struct Run {
    directory: PathBuf,
    owned: Vec<PathBuf>,
    names: HashSet<String>,
    sheets: Vec<SheetManifest>,
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
            for attempt in 1..=1000 {
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
            sheets: vec![],
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
        let mut chosen = None;
        for attempt in 1..=1000 {
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
                    chosen = Some((name, file));
                    break;
                }
                Err(Error::Io { source, .. })
                    if source.kind() == std::io::ErrorKind::AlreadyExists =>
                {
                    continue;
                }
                Err(error) => return Err(error),
            }
        }
        let (file, output) =
            chosen.ok_or_else(|| invalid("could not claim a distinct sheet filename"))?;
        let written = sheet.write(BufWriter::new(output))?;
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
        let mut json = self.file("manifest.json")?;
        serde_json::to_writer_pretty(&mut json, &manifest)?;
        json.write_all(b"\n")
            .map_err(|error| io("writing JSON manifest", error))?;
        json.flush()
            .map_err(|error| io("flushing JSON manifest", error))?;
        let mut text = self.file("manifest.txt")?;
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
}
