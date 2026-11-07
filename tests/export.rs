use ods2tsv::{Manifest, Options, ValueMode, export};
use std::{fs, io::Write, path::Path, process::Command};
use tempfile::TempDir;
use zip::{ZipWriter, write::SimpleFileOptions};

const HEADER: &str = "<office:document-content xmlns:office='urn:oasis:names:tc:opendocument:xmlns:office:1.0' xmlns:table='urn:oasis:names:tc:opendocument:xmlns:table:1.0' xmlns:text='urn:oasis:names:tc:opendocument:xmlns:text:1.0' xmlns:draw='urn:oasis:names:tc:opendocument:xmlns:drawing:1.0'><office:body><office:spreadsheet>";
const FOOTER: &str = "</office:spreadsheet></office:body></office:document-content>";

fn table(name: &str, rows: &str) -> String {
    format!("<table:table table:name='{name}'>{rows}</table:table>")
}
fn row(cells: &str) -> String {
    format!("<table:table-row>{cells}</table:table-row>")
}
fn cell(value: &str) -> String {
    format!(
        "<table:table-cell office:value-type='string'><text:p>{value}</text:p></table:table-cell>"
    )
}
fn xml(tables: &str) -> String {
    format!("{HEADER}{tables}{FOOTER}")
}
fn package(path: &Path, content: &str, extra: &[(&str, &str)]) {
    let mut zip = ZipWriter::new(fs::File::create(path).unwrap());
    for (name, text) in [
        ("mimetype", "application/vnd.oasis.opendocument.spreadsheet"),
        ("content.xml", content),
    ]
    .into_iter()
    .chain(extra.iter().copied())
    {
        zip.start_file(
            name,
            SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated),
        )
        .unwrap();
        zip.write_all(text.as_bytes()).unwrap();
    }
    zip.finish().unwrap();
}
fn convert(tables: &str, mode: ValueMode) -> (TempDir, ods2tsv::Export) {
    let dir = tempfile::Builder::new()
        .prefix("ods café ")
        .tempdir()
        .unwrap();
    let source = dir.path().join("source.ods");
    package(&source, &xml(tables), &[]);
    let result = export(
        &source,
        &Options {
            output: Some(dir.path().join("output")),
            values: mode,
        },
    )
    .unwrap();
    (dir, result)
}
fn records(output: &ods2tsv::Export, index: usize) -> Vec<Vec<String>> {
    csv::ReaderBuilder::new()
        .delimiter(b'\t')
        .has_headers(false)
        .from_path(output.directory.join(&output.manifest.sheets[index].file))
        .unwrap()
        .records()
        .map(|record| record.unwrap().iter().map(str::to_owned).collect())
        .collect()
}
fn failed(content: &str) -> String {
    let dir = tempfile::tempdir().unwrap();
    let source = dir.path().join("broken.ods");
    let destination = dir.path().join("output");
    package(&source, content, &[]);
    let error = export(
        &source,
        &Options {
            output: Some(destination.clone()),
            ..Options::default()
        },
    )
    .unwrap_err();
    assert!(
        !destination.exists(),
        "failed export left a directory: {error}"
    );
    assert!(source.exists());
    error.to_string()
}

#[test]
fn preserves_coordinates_and_rectangular_output() {
    let (_dir, output) = convert(
        &table(
            "Grid",
            &format!(
                "<table:table-row table:number-rows-repeated='2'/>{}{}<table:table-row table:number-rows-repeated='1048576'/>",
                row(&format!(
                    "<table:table-cell table:number-columns-repeated='2'/>{}",
                    cell("X")
                )),
                row(&cell("End"))
            ),
        ),
        ValueMode::SavedText,
    );
    assert_eq!(
        records(&output, 0),
        vec![
            vec!["", "", ""],
            vec!["", "", ""],
            vec!["", "", "X"],
            vec!["End", "", ""]
        ]
    );
    assert_eq!(
        (
            output.manifest.sheets[0].rows,
            output.manifest.sheets[0].columns
        ),
        (4, 3)
    );
}

#[test]
fn preserves_odf_text_and_excludes_non_cell_subtrees() {
    let payload = "<text:p>  First<text:span>   second </text:span>third  </text:p><text:p><text:s text:c='2'/>edge<text:s text:c='2'/></text:p><text:p>A<text:tab/>B<text:line-break/>C &amp; &#xE9;</text:p><office:annotation><text:p>Note</text:p></office:annotation><draw:frame><text:p>Drawing</text:p></draw:frame><table:table><table:table-row><table:table-cell><text:p>Nested</text:p></table:table-cell></table:table-row></table:table>";
    let (_dir, output) = convert(
        &table(
            "Text",
            &row(&format!("<table:table-cell>{payload}</table:table-cell>")),
        ),
        ValueMode::SavedText,
    );
    assert_eq!(
        records(&output, 0),
        vec![vec!["First second third\n  edge  \nA\tB\nC & é"]]
    );
    let bytes = fs::read(output.directory.join("Text.tsv")).unwrap();
    assert!(bytes.starts_with(b"\"First"));
    assert!(bytes.ends_with(b"\"\r\n"));
    assert_eq!(output.manifest.sheets.len(), 1);
}

#[test]
fn raw_values_remain_lexical_and_formulas_are_not_calculated() {
    let cells = "<table:table-cell office:value-type='float' office:value='12345678901234567890.123' table:formula='of:=1+1'><text:p>saved</text:p></table:table-cell><table:table-cell office:value-type='date' office:date-value='2026-11-07'><text:p>7 Nov</text:p></table:table-cell><table:table-cell office:value-type='float' office:value='7'/><table:table-cell office:value-type='float' office:value='9'><text:p/></table:table-cell><table:table-cell office:value-type='string' office:string-value=' raw '><text:p>display</text:p></table:table-cell>";
    let (_dir, text) = convert(&table("Values", &row(cells)), ValueMode::SavedText);
    assert_eq!(
        records(&text, 0),
        vec![vec!["saved", "7 Nov", "7", "", "display"]]
    );
    let (_dir, raw) = convert(&table("Values", &row(cells)), ValueMode::Raw);
    assert_eq!(
        records(&raw, 0),
        vec![vec![
            "12345678901234567890.123",
            "2026-11-07",
            "7",
            "9",
            " raw "
        ]]
    );
}

#[test]
fn merges_fill_spilled_rows_and_metadata_keeps_empty_outlying_merges() {
    let rows = format!(
        "{}<table:table-row table:number-rows-repeated='3'/>{}",
        row(
            "<table:table-cell table:number-rows-spanned='3' table:number-columns-spanned='2'><text:p>M</text:p></table:table-cell><table:covered-table-cell/>"
        ),
        row(
            "<table:table-cell table:number-columns-repeated='3'/><table:table-cell table:number-columns-spanned='2' table:number-rows-spanned='2'/>"
        )
    );
    let (_dir, output) = convert(&table("Merged", &rows), ValueMode::SavedText);
    assert_eq!(records(&output, 0), vec![vec!["M", "M"]; 3]);
    let merges = &output.manifest.sheets[0].merged_ranges;
    assert_eq!(merges.len(), 2);
    assert_eq!(
        (
            merges[0].start_row,
            merges[0].start_column,
            merges[0].end_row,
            merges[0].end_column
        ),
        (1, 1, 3, 2)
    );
    assert_eq!(
        (
            merges[1].start_row,
            merges[1].start_column,
            merges[1].end_row,
            merges[1].end_column
        ),
        (5, 4, 6, 5)
    );
    assert!(
        fs::read_to_string(output.directory.join("manifest.txt"))
            .unwrap()
            .contains("D5:E6")
    );
}

#[test]
fn repeated_rows_cells_and_merges_preserve_each_original_region() {
    let rows = "<table:table-row table:number-rows-repeated='3'><table:table-cell table:number-columns-spanned='2'><text:p>M</text:p></table:table-cell><table:covered-table-cell/><table:table-cell table:number-columns-repeated='2'><text:p>V</text:p></table:table-cell></table:table-row>";
    let (_dir, output) = convert(&table("Repeated", rows), ValueMode::SavedText);
    assert_eq!(records(&output, 0), vec![vec!["M", "M", "V", "V"]; 3]);
    assert_eq!(output.manifest.sheets[0].merged_ranges.len(), 3);
    assert_eq!(output.manifest.sheets[0].merged_ranges[2].start_row, 3);
}

#[test]
fn distinct_portable_names_empty_sheets_and_order_survive() {
    let names = ["Z", "A/B", "A_B", "a_b", "CON", "🦀 café", "Empty"];
    let tables: String = names
        .iter()
        .enumerate()
        .map(|(index, name)| {
            table(
                name,
                &if index == 6 {
                    String::new()
                } else {
                    row(&cell(&index.to_string()))
                },
            )
        })
        .collect();
    let (_dir, output) = convert(&tables, ValueMode::SavedText);
    assert_eq!(
        output
            .manifest
            .sheets
            .iter()
            .map(|sheet| sheet.name.as_str())
            .collect::<Vec<_>>(),
        names
    );
    assert_eq!(output.manifest.sheets[4].file, "_CON.tsv");
    let mut files = std::collections::HashSet::new();
    for (index, sheet) in output.manifest.sheets.iter().enumerate() {
        assert_eq!(sheet.position, index + 1);
        assert!(files.insert(sheet.file.to_lowercase()));
        assert!(output.directory.join(&sheet.file).is_file());
        if index != 6 {
            assert_eq!(records(&output, index), vec![vec![index.to_string()]]);
        }
    }
    assert_eq!(
        fs::metadata(output.directory.join("Empty.tsv"))
            .unwrap()
            .len(),
        0
    );
    assert_eq!(
        (
            output.manifest.sheets[6].rows,
            output.manifest.sheets[6].columns
        ),
        (0, 0)
    );
    let loaded: Manifest =
        serde_json::from_slice(&fs::read(output.directory.join("manifest.json")).unwrap()).unwrap();
    assert_eq!(loaded.sheets.len(), names.len());
    assert!(!output.directory.join(".incomplete").exists());
}

#[test]
fn giant_empty_tail_is_not_expanded_but_large_populated_output_is_refused() {
    let (_dir, output) = convert(
        &table(
            "Tail",
            &format!(
                "{}<table:table-row table:number-rows-repeated='1048575'><table:table-cell table:number-columns-repeated='16384'/></table:table-row>",
                row(&cell("Data"))
            ),
        ),
        ValueMode::SavedText,
    );
    assert_eq!(records(&output, 0), vec![vec!["Data"]]);
    let huge = xml(&table(
        "Huge",
        "<table:table-row table:number-rows-repeated='10000001'><table:table-cell><text:p>Data</text:p></table:table-cell></table:table-row>",
    ));
    assert!(failed(&huge).contains("rectangular output fields"));
}

#[test]
fn formula_warnings_distinguish_missing_from_saved_empty_results() {
    let rows = "<table:table-row table:number-rows-repeated='3'><table:table-cell table:formula='of:=1' table:number-columns-repeated='2'/><table:table-cell table:formula='of:=&quot;&quot;'><text:p/></table:table-cell></table:table-row>";
    let (_dir, output) = convert(&table("Formulas", rows), ValueMode::Raw);
    let sheet = &output.manifest.sheets[0];
    assert_eq!((sheet.rows, sheet.columns), (0, 0));
    assert_eq!(sheet.warnings.len(), 1);
    assert_eq!(sheet.warnings[0].count, 6);
}

#[test]
fn invalid_and_truncated_documents_cannot_leave_completed_exports() {
    let good_sheet = table("First", &row(&cell("Data")));
    for content in [
        format!("{HEADER}{good_sheet}"),
        format!("{HEADER}<table:table"),
        format!("{}<extra/>", xml(&good_sheet)),
        "<r/>".into(),
    ] {
        assert!(!failed(&content).is_empty());
    }
    assert!(
        failed(&xml(&table(
            "Bad repeat",
            "<table:table-row table:number-rows-repeated='0'/>"
        )))
        .contains("positive")
    );
    assert!(failed(&xml(&table("Overlap", &row("<table:table-cell table:number-columns-spanned='3'/><table:table-cell table:number-columns-spanned='2'/>")))).contains("overlapping"));
    assert!(
        failed(&format!(
            "<!DOCTYPE office:document-content [<!ENTITY x 'do not expand'>]>{}",
            xml(&table("DTD", &row(&cell("&x;"))))
        ))
        .contains("DTD")
    );
}

#[test]
fn existing_destinations_are_not_modified() {
    let dir = tempfile::tempdir().unwrap();
    let source = dir.path().join("input.ods");
    package(&source, &xml(&table("Sheet", &row(&cell("Data")))), &[]);
    let output = dir.path().join("existing");
    fs::create_dir(&output).unwrap();
    fs::write(output.join("sentinel"), b"keep").unwrap();
    assert!(
        export(
            &source,
            &Options {
                output: Some(output.clone()),
                ..Options::default()
            }
        )
        .is_err()
    );
    assert_eq!(fs::read(output.join("sentinel")).unwrap(), b"keep");
    assert_eq!(fs::read_dir(output).unwrap().count(), 1);
}

#[test]
fn only_encrypted_content_is_refused_not_unrelated_embedded_streams() {
    for (stream, refused) in [("content.xml", true), ("Pictures/secret", false)] {
        let dir = tempfile::tempdir().unwrap();
        let source = dir.path().join("input.ods");
        let manifest = format!(
            "<m:manifest xmlns:m='urn:oasis:names:tc:opendocument:xmlns:manifest:1.0'><m:file-entry m:full-path='{stream}'><m:encryption-data/></m:file-entry></m:manifest>"
        );
        package(
            &source,
            &xml(&table("Sheet", &row(&cell("Data")))),
            &[("META-INF/manifest.xml", &manifest)],
        );
        let result = export(
            &source,
            &Options {
                output: Some(dir.path().join("output")),
                ..Options::default()
            },
        );
        assert_eq!(result.is_err(), refused);
        if refused {
            assert!(result.unwrap_err().to_string().contains("encrypted"));
        }
    }
}

#[test]
fn flat_input_aliases_row_wrappers_and_utf16_work() {
    let original = xml(&table("Aliases", &format!("<table:table-header-rows>{}</table:table-header-rows><table:table-row-group>{}</table:table-row-group>", row(&cell("H")), row(&cell("café")))))
        .replace("<table:", "<t:").replace("</table:", "</t:")
        .replace(" table:", " t:").replace("xmlns:table=", "xmlns:t=");
    let dir = tempfile::tempdir().unwrap();
    let source = dir.path().join("renamed.data");
    let mut bytes = vec![0xff, 0xfe];
    for unit in original.encode_utf16() {
        bytes.extend_from_slice(&unit.to_le_bytes());
    }
    fs::write(&source, bytes).unwrap();
    let output = export(
        &source,
        &Options {
            output: Some(dir.path().join("output")),
            ..Options::default()
        },
    )
    .unwrap();
    assert_eq!(output.manifest.source.format, "fods");
    assert_eq!(records(&output, 0), vec![vec!["H"], vec!["café"]]);
}

#[test]
fn cli_reports_exit_codes_and_fresh_default_directories() {
    let binary = env!("CARGO_BIN_EXE_ods2tsv");
    assert_eq!(Command::new(binary).status().unwrap().code(), Some(2));
    let dir = tempfile::tempdir().unwrap();
    let source = dir.path().join("file with spaces.ods");
    package(&source, &xml(&table("Sheet", &row(&cell("Data")))), &[]);
    let mut destinations = Vec::new();
    for _ in 0..2 {
        let result = Command::new(binary)
            .arg(&source)
            .current_dir(dir.path())
            .output()
            .unwrap();
        assert!(result.status.success());
        let path = String::from_utf8(result.stdout).unwrap().trim().to_owned();
        assert!(dir.path().join(&path).join("manifest.json").is_file());
        destinations.push(path);
    }
    assert_ne!(destinations[0], destinations[1]);
    let failed = Command::new(binary)
        .arg(dir.path().join("missing"))
        .output()
        .unwrap();
    assert_eq!(failed.status.code(), Some(1));
    assert!(failed.stdout.is_empty());
    assert!(
        String::from_utf8(failed.stderr)
            .unwrap()
            .contains("opening")
    );
}

#[test]
fn cell_byte_limit_counts_only_exported_paragraph_separators() {
    let text = "x".repeat(ods2tsv::MAX_CELL_BYTES);
    let (_dir, output) = convert(&table("Limit", &row(&cell(&text))), ValueMode::SavedText);
    assert_eq!(records(&output, 0)[0][0], text);
    let paragraphs = format!(
        "<table:table-cell><text:p>{}</text:p><text:p>x</text:p></table:table-cell>",
        "x".repeat(ods2tsv::MAX_CELL_BYTES - 2)
    );
    let (_dir, output) = convert(&table("Limit", &row(&paragraphs)), ValueMode::SavedText);
    assert_eq!(records(&output, 0)[0][0].len(), ods2tsv::MAX_CELL_BYTES);
    let error = failed(&xml(&table("Limit", &row(&cell(&(text + "x"))))));
    assert!(error.contains("cell exceeds"), "{error}");
}

#[test]
fn many_colliding_sheet_names_keep_unique_manifest_mappings() {
    let body = table("Duplicate", &row(&cell("value"))).repeat(1002);
    let (_dir, output) = convert(&body, ValueMode::SavedText);
    let files: std::collections::HashSet<_> = output
        .manifest
        .sheets
        .iter()
        .map(|sheet| sheet.file.to_lowercase())
        .collect();
    assert_eq!(files.len(), 1002);
    assert_eq!(output.manifest.sheets[1001].file, "Duplicate (1002).tsv");
    assert_eq!(records(&output, 1001), vec![vec!["value"]]);
}

#[test]
fn explicit_whitespace_separates_ordinary_space_runs() {
    let paragraphs = [
        ("a<text:tab/> b", "a\t b"),
        ("a<text:line-break/> b", "a\n b"),
        ("a<text:s/> b", "a  b"),
        (" <text:tab/>  b ", "\t b"),
        ("a <text:s text:c='2'/>  b", "a    b"),
        ("a<text:tab/> ", "a\t"),
        (" a   <text:span> b </text:span> c ", "a b c"),
    ];
    let cells: String = paragraphs.iter().map(|(text, _)| cell(text)).collect();
    for mode in [ValueMode::SavedText, ValueMode::Raw] {
        let (_dir, output) = convert(&table("Spaces", &row(&cells)), mode);
        assert_eq!(
            records(&output, 0),
            vec![
                paragraphs
                    .iter()
                    .map(|(_, value)| *value)
                    .collect::<Vec<_>>()
            ]
        );
    }
}

#[test]
fn ruby_annotations_and_note_bodies_do_not_enter_paragraph_values() {
    let payload = "<text:ruby><text:ruby-base>base</text:ruby-base><text:ruby-text>annotation</text:ruby-text></text:ruby> a<text:note><text:note-citation>1</text:note-citation><text:note-body><text:p>footnote</text:p></text:note-body></text:note>b";
    let (_dir, output) = convert(&table("Text", &row(&cell(payload))), ValueMode::SavedText);
    assert_eq!(records(&output, 0), vec![vec!["base a1b"]]);
}

#[test]
fn cached_errors_keep_text_and_coordinates_in_both_modes() {
    let error = "<table:table-cell xmlns:e='urn:org:documentfoundation:names:experimental:calc:xmlns:calcext:1.0' e:value-type='error' office:value-type='string' office:string-value='' table:formula='of:=1/0'><text:p>#DIV/0!</text:p></table:table-cell>";
    let missing = "<table:table-cell xmlns:e='urn:org:documentfoundation:names:experimental:calc:xmlns:calcext:1.0' e:value-type='error' office:value-type='string' office:string-value='' table:formula='of:=1/0'><text:p/></table:table-cell>";
    let valid_empty = "<table:table-cell office:value-type='string' office:string-value='' table:formula='of:=&quot;&quot;'><text:p/></table:table-cell>";
    for mode in [ValueMode::SavedText, ValueMode::Raw] {
        let (_dir, output) = convert(
            &table(
                "Error",
                &(row(&(cell("ok") + error)) + &row(&(valid_empty.to_owned() + missing))),
            ),
            mode,
        );
        assert_eq!(records(&output, 0), vec![vec!["ok", "#DIV/0!"]]);
        assert_eq!(output.manifest.sheets[0].columns, 2);
        assert_eq!(output.manifest.sheets[0].warnings.len(), 1);
        assert_eq!(
            output.manifest.sheets[0].warnings[0].code,
            "missing-formula-result"
        );
        assert_eq!(output.manifest.sheets[0].warnings[0].count, 1);
    }
    // A string that resembles an error is still an ordinary valid stored empty result.
    let ordinary = "<table:table-cell office:value-type='string' office:string-value=''><text:p>#DIV/0!</text:p></table:table-cell>";
    let (_dir, output) = convert(
        &table("Not an error", &row(&(cell("ok") + ordinary))),
        ValueMode::Raw,
    );
    assert_eq!(records(&output, 0), vec![vec!["ok"]]);
}

#[test]
fn large_ignored_content_does_not_consume_a_cell_budget() {
    let ignored = "A".repeat(ods2tsv::MAX_CELL_BYTES + 4);
    let extras = format!(
        "<draw:frame><draw:image office:name='{ignored}'><office:binary-data>{ignored}</office:binary-data></draw:image></draw:frame><office:annotation><text:p>{ignored}</text:p></office:annotation><table:table><table:table-row>{}</table:table-row></table:table>",
        cell(&ignored)
    );
    let content = xml(&table(
        "Content",
        &row(&format!(
            "<table:table-cell><text:p>ok</text:p>{extras}</table:table-cell>"
        )),
    ));
    for flat in [false, true] {
        let dir = tempfile::tempdir().unwrap();
        let source = dir
            .path()
            .join(if flat { "large.fods" } else { "large.ods" });
        if flat {
            fs::write(&source, &content).unwrap();
        } else {
            package(&source, &content, &[]);
        }
        let output = export(
            &source,
            &Options {
                output: Some(dir.path().join("out")),
                ..Options::default()
            },
        )
        .unwrap();
        assert_eq!(records(&output, 0), vec![vec!["ok"]]);
    }
}

#[test]
fn oversized_cells_have_a_specific_error_and_clean_up() {
    for excess in [1, 2, 1024] {
        let value = "x".repeat(ods2tsv::MAX_CELL_BYTES + excess);
        for payload in [
            cell(&value),
            format!("<table:table-cell office:value-type='string' office:string-value='{value}'/>"),
        ] {
            let error = failed(&xml(&table("Too much text", &row(&payload))));
            assert!(error.contains("cell exceeds"), "{error}");
        }
    }
}

#[test]
fn covered_content_is_discarded_in_favor_of_the_merge_anchor() {
    for (anchor, expected) in [("", vec![]), ("anchor", vec![vec!["anchor", "anchor"]])] {
        let cells = format!(
            "<table:table-cell table:number-columns-spanned='2'><text:p>{anchor}</text:p></table:table-cell><table:covered-table-cell><text:p>alternate</text:p></table:covered-table-cell>"
        );
        let (_dir, output) = convert(&table("Merged", &row(&cells)), ValueMode::SavedText);
        assert_eq!(records(&output, 0), expected);
        assert_eq!(output.manifest.sheets[0].merged_ranges.len(), 1);
    }
}

#[test]
fn buffered_package_reads_still_reject_a_bad_content_checksum() {
    let (dir, good) = convert(&table("CRC", &row(&cell("ok"))), ValueMode::SavedText);
    assert_eq!(records(&good, 0), vec![vec!["ok"]]);
    let source = dir.path().join("source.ods");
    let mut bytes = fs::read(&source).unwrap();
    // content.xml is the helper's final member. Change only its central-directory CRC field.
    let entry = bytes
        .windows(4)
        .rposition(|window| window == b"PK\x01\x02")
        .unwrap();
    bytes[entry + 16] ^= 1;
    fs::write(&source, bytes).unwrap();
    let destination = dir.path().join("invalid-crc");
    let error = export(
        &source,
        &Options {
            output: Some(destination.clone()),
            ..Options::default()
        },
    )
    .unwrap_err();
    assert!(error.to_string().contains("checksum"), "{error}");
    assert!(!destination.exists());
}
