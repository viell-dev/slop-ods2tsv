use criterion::{BatchSize, Criterion, criterion_group, criterion_main};
use ods2tsv::{Options, export};
use std::{fs, time::Duration};

fn fixture(body: &str) -> String {
    format!(
        "<office:document-content xmlns:office='urn:oasis:names:tc:opendocument:xmlns:office:1.0' xmlns:table='urn:oasis:names:tc:opendocument:xmlns:table:1.0' xmlns:text='urn:oasis:names:tc:opendocument:xmlns:text:1.0'><office:body><office:spreadsheet><table:table table:name='Bench'>{body}</table:table></office:spreadsheet></office:body></office:document-content>"
    )
}
fn benchmarks(c: &mut Criterion) {
    let value = "<table:table-cell><text:p>Value</text:p></table:table-cell>";
    let dense = format!("<table:table-row>{}</table:table-row>", value.repeat(12)).repeat(2000);
    let cases = [
        ("dense-24000-fields", dense, 2000, 12),
        ("repeated-1000000-fields", "<table:table-row table:number-rows-repeated='100000'><table:table-cell table:number-columns-repeated='10'><text:p>V</text:p></table:table-cell></table:table-row>".to_owned(), 100000, 10),
        ("empty-million-row-tail", format!("<table:table-row>{value}</table:table-row><table:table-row table:number-rows-repeated='1048575'><table:table-cell table:number-columns-repeated='16384'/></table:table-row>"), 1, 1),
        ("sparse-100000-fields", format!("<table:table-row table:number-rows-repeated='199'/><table:table-row><table:table-cell table:number-columns-repeated='499'/>{value}</table:table-row>"), 200, 500),
        ("merged-10000-regions", "<table:table-row table:number-rows-repeated='10000'><table:table-cell table:number-columns-spanned='2'><text:p>M</text:p></table:table-cell><table:covered-table-cell/></table:table-row>".into(), 10000, 2),
    ];
    for (name, body, rows, columns) in cases {
        let input = tempfile::tempdir().unwrap();
        let source = input.path().join("bench.fods");
        fs::write(&source, fixture(&body)).unwrap();
        eprintln!(
            "Fixture {name}: {} input bytes, {rows} rows, {columns} columns",
            fs::metadata(&source).unwrap().len()
        );
        c.bench_function(name, |b| {
            b.iter_batched(
                || tempfile::tempdir().unwrap(),
                |directory| {
                    let result = export(
                        &source,
                        &Options {
                            output: Some(directory.path().join("out")),
                            ..Options::default()
                        },
                    )
                    .unwrap();
                    assert_eq!(
                        (
                            result.manifest.sheets[0].rows,
                            result.manifest.sheets[0].columns
                        ),
                        (rows, columns)
                    );
                    (directory, result)
                },
                BatchSize::PerIteration,
            )
        });
    }
}
criterion_group! { name = benches; config = Criterion::default().sample_size(10).warm_up_time(Duration::from_secs(1)).measurement_time(Duration::from_secs(2)); targets = benchmarks }
criterion_main!(benches);
