use crate::{Error, MAX_CELLS, MAX_MERGES, MergedRange, Warning, invalid};
use std::{
    cmp::Reverse,
    collections::{BTreeMap, BinaryHeap},
    io::Write,
};

#[derive(Debug)]
pub(crate) struct Cell {
    pub column: usize,
    pub repeat: usize,
    pub row_span: usize,
    pub column_span: usize,
    pub value: String,
    pub missing_formula: bool,
}

#[derive(Debug)]
pub(crate) struct Row {
    pub start: usize,
    pub repeat: usize,
    pub cells: Vec<Cell>,
}
#[derive(Debug)]
pub(crate) struct Sheet {
    pub name: String,
    pub rows: Vec<Row>,
}

struct Merge<'a> {
    range: MergedRange,
    value: &'a str,
}

pub(crate) struct Written {
    pub rows: usize,
    pub columns: usize,
    pub ranges: Vec<MergedRange>,
    pub warnings: Vec<Warning>,
}

pub(crate) fn add(a: usize, b: usize) -> Result<usize, Error> {
    a.checked_add(b)
        .ok_or_else(|| invalid("spreadsheet coordinate overflow"))
}

impl Sheet {
    pub fn write(&self, output: impl Write) -> Result<Written, Error> {
        let mut height = 0;
        let mut width = 0;
        let mut merges = Vec::new();
        let mut missing = 0usize;
        for row in &self.rows {
            for cell in &row.cells {
                if cell.missing_formula {
                    missing = missing
                        .checked_add(
                            row.repeat
                                .checked_mul(cell.repeat)
                                .ok_or_else(|| invalid("formula count overflow"))?,
                        )
                        .ok_or_else(|| invalid("formula count overflow"))?;
                }
                if !cell.value.is_empty() {
                    height = height.max(add(add(row.start, row.repeat - 1)?, cell.row_span)?);
                    width = width.max(add(add(cell.column, cell.repeat - 1)?, cell.column_span)?);
                }
                if cell.row_span > 1 || cell.column_span > 1 {
                    let count = row
                        .repeat
                        .checked_mul(cell.repeat)
                        .ok_or_else(|| invalid("merged range count overflow"))?;
                    if count > MAX_MERGES.saturating_sub(merges.len()) {
                        return Err(invalid(format!(
                            "sheet {:?} exceeds {MAX_MERGES} merged ranges",
                            self.name
                        )));
                    }
                    for r in row.start..add(row.start, row.repeat)? {
                        for c in cell.column..add(cell.column, cell.repeat)? {
                            merges.push(Merge {
                                range: MergedRange {
                                    start_row: add(r, 1)?,
                                    start_column: add(c, 1)?,
                                    end_row: add(r, cell.row_span)?,
                                    end_column: add(c, cell.column_span)?,
                                },
                                value: &cell.value,
                            });
                        }
                    }
                }
            }
        }
        if height
            .checked_mul(width)
            .is_none_or(|cells| cells > MAX_CELLS)
        {
            return Err(invalid(format!(
                "sheet {:?} exceeds {MAX_CELLS} rectangular output fields",
                self.name
            )));
        }
        merges.sort_by_key(|merge| (merge.range.start_row, merge.range.start_column));
        // A sweep checks overlap without allocating a dense grid, including empty merges beyond TSV bounds.
        let mut active: BTreeMap<usize, &Merge<'_>> = BTreeMap::new();
        let mut expiry = BinaryHeap::<Reverse<(usize, usize)>>::new();
        for merge in &merges {
            while expiry
                .peek()
                .is_some_and(|Reverse((end, _))| *end < merge.range.start_row)
            {
                let Reverse((_, column)) = expiry.pop().unwrap();
                active.remove(&column);
            }
            if active
                .range(..=merge.range.end_column)
                .next_back()
                .is_some_and(|(_, other)| other.range.end_column >= merge.range.start_column)
            {
                return Err(invalid(format!(
                    "sheet {:?} contains overlapping merged ranges",
                    self.name
                )));
            }
            active.insert(merge.range.start_column, merge);
            expiry.push(Reverse((merge.range.end_row, merge.range.start_column)));
        }
        active.clear();
        expiry.clear();
        let mut next_merge = 0;
        let mut next_row = 0;
        let mut loaded_row = None;
        let mut values = Vec::new();
        let mut writer = csv::WriterBuilder::new()
            .delimiter(b'\t')
            .has_headers(false)
            .terminator(csv::Terminator::CRLF)
            .from_writer(output);
        for r in 0..height {
            while next_row < self.rows.len()
                && add(self.rows[next_row].start, self.rows[next_row].repeat)? <= r
            {
                next_row += 1;
            }
            let mut fields = vec![""; width];
            if let Some(row) = self.rows.get(next_row).filter(|row| row.start <= r) {
                if loaded_row != Some(next_row) {
                    values.clear();
                    values.extend(
                        row.cells
                            .iter()
                            .filter(|cell| !cell.value.is_empty() && cell.column < width),
                    );
                    loaded_row = Some(next_row);
                }
                for cell in &values {
                    fields[cell.column..add(cell.column, cell.repeat)?.min(width)]
                        .fill(&cell.value);
                }
            }
            while expiry.peek().is_some_and(|Reverse((end, _))| *end <= r) {
                let Reverse((_, column)) = expiry.pop().unwrap();
                active.remove(&column);
            }
            while next_merge < merges.len() && merges[next_merge].range.start_row <= r + 1 {
                let merge = &merges[next_merge];
                active.insert(merge.range.start_column, merge);
                expiry.push(Reverse((merge.range.end_row, merge.range.start_column)));
                next_merge += 1;
            }
            for (_, merge) in active.range(..=width) {
                let start = merge.range.start_column - 1;
                if start < width {
                    fields[start..merge.range.end_column.min(width)].fill(merge.value);
                }
            }
            writer.write_record(fields)?;
        }
        writer
            .flush()
            .map_err(|error| crate::io("flushing TSV", error))?;
        let warnings = if missing == 0 {
            vec![]
        } else {
            vec![Warning {
            code: "missing-formula-result".into(), count: missing,
            message: "Formula cells have neither saved text nor a stored result; exported as empty values.".into(),
        }]
        };
        Ok(Written {
            rows: height,
            columns: width,
            ranges: merges.into_iter().map(|merge| merge.range).collect(),
            warnings,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    #[test]
    fn sink_failure_is_not_reported_as_success() {
        struct Fails;
        impl Write for Fails {
            fn write(&mut self, _: &[u8]) -> std::io::Result<usize> {
                Err(std::io::Error::other("synthetic write failure"))
            }
            fn flush(&mut self) -> std::io::Result<()> {
                Err(std::io::Error::other("synthetic flush failure"))
            }
        }
        let sheet = Sheet {
            name: "failure".into(),
            rows: vec![Row {
                start: 0,
                repeat: 1,
                cells: vec![Cell {
                    column: 0,
                    repeat: 1,
                    row_span: 1,
                    column_span: 1,
                    value: "value".into(),
                    missing_formula: false,
                }],
            }],
        };
        assert!(sheet.write(Fails).is_err());
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(128))]
        #[test]
        fn repeated_values_match_simple_expansion(values in prop::collection::vec("[a-z]{0,4}", 1..12), repeat in 1usize..8) {
            let cells = values.iter().enumerate().map(|(column, value)| Cell {
                column, repeat: 1, row_span: 1, column_span: 1, value: value.clone(), missing_formula: false,
            }).collect();
            let sheet = Sheet { name: "generated".into(), rows: vec![Row { start: 0, repeat, cells }] };
            let mut bytes = Vec::new();
            let written = sheet.write(&mut bytes).unwrap();
            let width = values.iter().rposition(|value| !value.is_empty()).map_or(0, |position| position + 1);
            let expected = if width == 0 { vec![] } else { vec![values[..width].to_vec(); repeat] };
            let actual: Vec<Vec<String>> = csv::ReaderBuilder::new().delimiter(b'\t').has_headers(false)
                .from_reader(bytes.as_slice()).records().map(|record| record.unwrap().iter().map(str::to_owned).collect()).collect();
            prop_assert_eq!(actual, expected);
            prop_assert_eq!(written.columns, width);
        }

        #[test]
        fn vertical_merges_match_a_dense_reference(values in prop::collection::vec(("[a-z]{0,3}", 1usize..6), 1..10)) {
            let cells = values.iter().enumerate().map(|(column, (value, height))| Cell {
                column, repeat: 1, row_span: *height, column_span: 1, value: value.clone(), missing_formula: false,
            }).collect();
            let sheet = Sheet { name: "generated merges".into(), rows: vec![Row { start: 0, repeat: 1, cells }] };
            let width = values.iter().rposition(|(value, _)| !value.is_empty()).map_or(0, |column| column + 1);
            let height = values.iter().filter(|(value, _)| !value.is_empty()).map(|(_, height)| *height).max().unwrap_or(0);
            let expected: Vec<Vec<String>> = (0..height).map(|r| values[..width].iter()
                .map(|(value, extent)| if r < *extent { value.clone() } else { String::new() }).collect()).collect();
            let mut bytes = Vec::new();
            let written = sheet.write(&mut bytes).unwrap();
            let actual: Vec<Vec<String>> = csv::ReaderBuilder::new().delimiter(b'\t').has_headers(false)
                .from_reader(bytes.as_slice()).records().map(|record| record.unwrap().iter().map(str::to_owned).collect()).collect();
            prop_assert_eq!(actual, expected);
            prop_assert_eq!(written.ranges.len(), values.iter().filter(|(_, extent)| *extent > 1).count());
        }
    }
}
