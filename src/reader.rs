use crate::{
    Error, MAX_CELL_BYTES, invalid,
    sheet::{Cell, Row, Sheet, add},
};
use serde::{Deserialize, Serialize};
use std::io::Read;
use xml::{
    attribute::OwnedAttribute,
    name::OwnedName,
    reader::{ParserConfig, XmlEvent},
};

const OFFICE: &str = "urn:oasis:names:tc:opendocument:xmlns:office:1.0";
const TABLE: &str = "urn:oasis:names:tc:opendocument:xmlns:table:1.0";
const TEXT: &str = "urn:oasis:names:tc:opendocument:xmlns:text:1.0";
const DRAW: &str = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0";

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ValueMode {
    #[default]
    SavedText,
    Raw,
}

impl ValueMode {
    pub(crate) fn label(self) -> &'static str {
        match self {
            Self::SavedText => "saved-text",
            Self::Raw => "raw",
        }
    }
}

fn is(name: &OwnedName, ns: &str, local: &str) -> bool {
    name.namespace.as_deref() == Some(ns) && name.local_name == local
}

fn attr<'a>(attributes: &'a [OwnedAttribute], ns: &str, local: &str) -> Option<&'a str> {
    attributes
        .iter()
        .find(|attribute| is(&attribute.name, ns, local))
        .map(|attribute| attribute.value.as_str())
}

fn count(attributes: &[OwnedAttribute], ns: &str, local: &str) -> Result<usize, Error> {
    attr(attributes, ns, local).map_or(Ok(1), |value| {
        value
            .parse::<usize>()
            .ok()
            .filter(|value| *value > 0)
            .ok_or_else(|| invalid(format!("{local} must be a positive supported integer")))
    })
}

struct Pending {
    cell: Cell,
    covered: bool,
    raw: Option<String>,
    formula: bool,
    paragraphs: Vec<String>,
    paragraph_depth: usize,
    pending_space: bool,
    last_space: bool,
    bytes: usize,
}

impl Pending {
    fn start(attributes: &[OwnedAttribute], column: usize, covered: bool) -> Result<Self, Error> {
        let raw_attribute = match attr(attributes, OFFICE, "value-type") {
            Some("float" | "percentage" | "currency") => "value",
            Some("date") => "date-value",
            Some("time") => "time-value",
            Some("boolean") => "boolean-value",
            Some("string") => "string-value",
            _ => "",
        };
        Ok(Self {
            cell: Cell {
                column,
                repeat: count(attributes, TABLE, "number-columns-repeated")?,
                row_span: count(attributes, TABLE, "number-rows-spanned")?,
                column_span: count(attributes, TABLE, "number-columns-spanned")?,
                value: String::new(),
                missing_formula: false,
            },
            covered,
            raw: attr(attributes, OFFICE, raw_attribute).map(str::to_owned),
            formula: attr(attributes, TABLE, "formula").is_some(),
            paragraphs: vec![],
            paragraph_depth: 0,
            pending_space: false,
            last_space: true,
            bytes: 0,
        })
    }

    fn push(&mut self, value: &str) -> Result<(), Error> {
        self.bytes = add(self.bytes, value.len())?;
        if self.bytes > MAX_CELL_BYTES {
            return Err(invalid(format!("cell exceeds {MAX_CELL_BYTES} text bytes")));
        }
        if let Some(paragraph) = self.paragraphs.last_mut() {
            paragraph.push_str(value);
        }
        Ok(())
    }

    fn characters(&mut self, text: &str) -> Result<(), Error> {
        if self.covered || self.paragraph_depth == 0 {
            return Ok(());
        }
        for ch in text.chars() {
            if matches!(ch, ' ' | '\t' | '\r' | '\n') {
                if !self.last_space {
                    self.pending_space = true;
                    self.last_space = true;
                }
            } else {
                if self.pending_space {
                    self.push(" ")?;
                    self.pending_space = false;
                }
                self.push(ch.encode_utf8(&mut [0; 4]))?;
                self.last_space = false;
            }
        }
        Ok(())
    }

    fn explicit(&mut self, ch: char, repeat: usize) -> Result<(), Error> {
        if self.covered || self.paragraph_depth == 0 {
            return Ok(());
        }
        if repeat > MAX_CELL_BYTES.saturating_sub(self.bytes) {
            return Err(invalid("explicit whitespace exceeds cell text limit"));
        }
        if self.pending_space {
            self.push(" ")?;
            self.pending_space = false;
        }
        self.push(&ch.to_string().repeat(repeat))?;
        self.last_space = true;
        Ok(())
    }

    fn finish(mut self, mode: ValueMode) -> Result<Cell, Error> {
        if !self.covered {
            self.cell.missing_formula =
                self.formula && self.raw.is_none() && self.paragraphs.is_empty();
            let display = (!self.paragraphs.is_empty()).then(|| self.paragraphs.join("\n"));
            self.cell.value = match mode {
                ValueMode::SavedText => display.or(self.raw),
                ValueMode::Raw => self.raw.or(display),
            }
            .unwrap_or_default();
            if self.cell.value.len() > MAX_CELL_BYTES {
                return Err(invalid("cell exceeds text limit"));
            }
        }
        Ok(self.cell)
    }
}

/// The dependency owns XML validity, decoding, namespaces and references. This loop owns ODF projection.
pub(crate) fn read(
    source: impl Read,
    mode: ValueMode,
    mut emit: impl FnMut(Sheet) -> Result<(), Error>,
) -> Result<(), Error> {
    let parser = ParserConfig::new()
        .allow_multiple_root_elements(false)
        .whitespace_to_characters(true)
        .cdata_to_characters(true)
        .max_data_length(MAX_CELL_BYTES)
        .max_attribute_length(MAX_CELL_BYTES)
        .max_entity_expansion_length(MAX_CELL_BYTES)
        .max_entity_expansion_depth(4)
        .create_reader(source);
    let mut stack = Vec::<OwnedName>::new();
    let mut sheet: Option<Sheet> = None;
    let mut row: Option<Row> = None;
    let mut cell: Option<Pending> = None;
    let mut row_index = 0usize;
    let mut column = 0usize;
    let mut skip = 0usize;
    let mut spreadsheet = false;
    let mut end_document = false;
    for event in parser {
        match event? {
            XmlEvent::StartElement {
                name, attributes, ..
            } => {
                if stack.is_empty() {
                    if !(is(&name, OFFICE, "document") || is(&name, OFFICE, "document-content")) {
                        return Err(invalid("input is not an OpenDocument spreadsheet"));
                    }
                    if let Some(mime) = attr(&attributes, OFFICE, "mimetype") {
                        if !matches!(
                            mime,
                            "application/vnd.oasis.opendocument.spreadsheet"
                                | "application/vnd.oasis.opendocument.spreadsheet-template"
                        ) {
                            return Err(invalid("input declares a non-spreadsheet document type"));
                        }
                    }
                }
                if skip > 0 {
                    skip += 1;
                    stack.push(name);
                    continue;
                }
                let ignored = name.namespace.as_deref().is_some_and(|ns| {
                    ns == DRAW || ns == "urn:oasis:names:tc:opendocument:xmlns:dr3d:1.0"
                }) || is(&name, OFFICE, "annotation")
                    || is(&name, TABLE, "tracked-changes")
                    || (sheet.is_some() && is(&name, TABLE, "table"));
                if ignored {
                    skip = 1;
                    stack.push(name);
                    continue;
                }
                if is(&name, OFFICE, "spreadsheet")
                    && stack
                        .last()
                        .is_some_and(|parent| is(parent, OFFICE, "body"))
                {
                    if spreadsheet {
                        return Err(invalid("multiple spreadsheet bodies are unsupported"));
                    }
                    spreadsheet = true;
                } else if is(&name, TABLE, "table")
                    && stack
                        .last()
                        .is_some_and(|parent| is(parent, OFFICE, "spreadsheet"))
                {
                    sheet = Some(Sheet {
                        name: attr(&attributes, TABLE, "name").unwrap_or_default().into(),
                        rows: vec![],
                    });
                    row_index = 0;
                } else if sheet.is_some()
                    && is(&name, TABLE, "table-row")
                    && row.is_none()
                    && cell.is_none()
                {
                    row = Some(Row {
                        start: row_index,
                        repeat: count(&attributes, TABLE, "number-rows-repeated")?,
                        cells: vec![],
                    });
                    column = 0;
                } else if row.is_some()
                    && cell.is_none()
                    && (is(&name, TABLE, "table-cell") || is(&name, TABLE, "covered-table-cell"))
                {
                    cell = Some(Pending::start(
                        &attributes,
                        column,
                        is(&name, TABLE, "covered-table-cell"),
                    )?);
                } else if let Some(pending) = cell.as_mut().filter(|pending| !pending.covered) {
                    if is(&name, TEXT, "p") || is(&name, TEXT, "h") {
                        if pending.paragraph_depth == 0 {
                            pending.bytes = add(pending.bytes, 1)?;
                            if pending.bytes > MAX_CELL_BYTES {
                                return Err(invalid("cell exceeds text limit"));
                            }
                            pending.paragraphs.push(String::new());
                            pending.pending_space = false;
                            pending.last_space = true;
                        }
                        pending.paragraph_depth += 1;
                    } else if is(&name, TEXT, "s") {
                        pending.explicit(' ', count(&attributes, TEXT, "c")?)?;
                    } else if is(&name, TEXT, "tab") {
                        pending.explicit('\t', 1)?;
                    } else if is(&name, TEXT, "line-break") {
                        pending.explicit('\n', 1)?;
                    }
                }
                stack.push(name);
            }
            XmlEvent::EndElement { name } => {
                if skip > 0 {
                    skip -= 1;
                    stack.pop();
                    continue;
                }
                if is(&name, TABLE, "table") {
                    if let Some(complete) = sheet.take() {
                        emit(complete)?;
                    }
                } else if is(&name, TABLE, "table-row") {
                    if let (Some(sheet), Some(row)) = (sheet.as_mut(), row.take()) {
                        row_index = add(row.start, row.repeat)?;
                        sheet.rows.push(row);
                    }
                } else if is(&name, TABLE, "table-cell") || is(&name, TABLE, "covered-table-cell") {
                    if let (Some(row), Some(pending)) = (row.as_mut(), cell.take()) {
                        column = add(column, pending.cell.repeat)?;
                        row.cells.push(pending.finish(mode)?);
                    }
                } else if (is(&name, TEXT, "p") || is(&name, TEXT, "h")) && cell.is_some() {
                    let pending = cell.as_mut().unwrap();
                    pending.paragraph_depth = pending.paragraph_depth.saturating_sub(1);
                    if pending.paragraph_depth == 0 {
                        pending.pending_space = false;
                    }
                }
                stack.pop();
            }
            XmlEvent::Characters(text) | XmlEvent::CData(text) | XmlEvent::Whitespace(text)
                if skip == 0 =>
            {
                if let Some(pending) = cell.as_mut() {
                    pending.characters(&text)?;
                }
            }
            XmlEvent::Doctype { .. } => {
                return Err(invalid("DTD declarations are unsupported in workbook XML"));
            }
            XmlEvent::EndDocument => {
                end_document = true;
            }
            _ => {}
        }
    }
    if !spreadsheet || !end_document || !stack.is_empty() {
        return Err(invalid("input has no complete spreadsheet body"));
    }
    Ok(())
}
