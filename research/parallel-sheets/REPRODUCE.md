# Reproduce the archived experiment

This is historical research against beta.1 commit
`e1807728d6e92b699cab0a859b29092da4946309`. It has known correctness failures and is not a
supported exporter. The production tool has no Rayon/quick-xml dependency or research option.
The patch contains the complete scratch changes, including the exact dependency lock changes.

The recorded measurements used Linux GNU, Rust 1.99.1, Python 3.13.5, six CPU quota and 3 GiB RAM.
They include full exports with warm filesystem caches. See the [report](README.md) for host,
method, limitations and all results. They do not measure the Windows or released musl binary.

## Build in disposable Linux Docker

Use a new lab directory and Linux containers. From the repository root in PowerShell:

```powershell
$kit = (Resolve-Path research/parallel-sheets).Path
$lab = Join-Path (Get-Location).Path artifacts/parallel-rerun
New-Item -ItemType Directory -Path $lab -ErrorAction Stop
git archive --format=tar --output "$lab/source-beta1.tar" e1807728d6e92b699cab0a859b29092da4946309
docker build --tag ods2tsv-parallel-research "$kit"
docker run --rm --cpus 6 --memory 3g `
  --mount "type=bind,src=$kit,dst=/kit,readonly" `
  --mount "type=bind,src=$lab,dst=/lab" `
  ods2tsv-parallel-research bash /kit/build.sh
```

On a Linux host, resolve the same two absolute paths, create the archive with ordinary Git,
and use Bash line continuations instead of PowerShell backticks. Both source trees, binaries,
Cargo downloads and generated results stay in the lab, outside the current checkout. The
builder refuses to reuse an existing base/prototype tree. An optional read-only Cargo registry
cache can be mounted at `/cache`; it is copied before use. The convenience Dockerfile uses the
official Rust 1.99.1 slim image with Python/GNU time/patch installed. It is an equivalent rerun
environment, not the exact image used for the recorded measurements; retain its actual versions.

The archive hash originally measured was
`fdc86a48a44e9b511edce3c2ee41fcc90f91c29dfc90330b1838a53144b0250a`.
The baseline is built independently, then the complete patch is applied to a separate copy.
Both use `--release --locked`; the prototype uses Rayon 1.12.0 and quick-xml 0.42.0.
The normal prototype suite runs with its hook disabled and passes all 40 tests.

## Run the synthetic stages

Keep the same `$kit` and `$lab` variables. First generate the fixed fixtures, then choose stages:

```powershell
foreach ($stage in @('generate', 'timing', 'correctness', 'failures', 'probes', 'extra', 'summary')) {
  docker run --rm --network none --cpus 6 --memory 3g `
    --mount "type=bind,src=$kit,dst=/kit,readonly" `
    --mount "type=bind,src=$lab,dst=/lab" `
    ods2tsv-parallel-research bash /kit/run.sh $stage
  if ($LASTEXITCODE -ne 0) { throw "Research stage failed: $stage" }
}
```

`timing` includes one warmup and three rotating-order measured runs per variant. `extra` adds
two measured rounds to four cheap cases. Every timed child includes startup, decompression,
indexing/validation, pool creation, parsing, ordered TSV output and manifests. Generation,
comparison and deletion are outside the interval. Do not benchmark containers concurrently.

`runner.py` generates the public fixtures with fixed content; ZIP timestamps can change archive
hashes on regeneration. Dense cases hold 120,000 ordinary cells and 20,000 row templates fixed
while changing sheet count. Exact comparisons normalize only the export timestamp. CPU and
peak RSS are measured for the converter child using GNU time, not for fixture generation.
The scripts append results; use a fresh lab for an independent measurement set.

`probes` records the known namespace/context gaps without asserting that the prototype is
compatible. Inspect `results/probes.jsonl` and the report. To see the existing-suite failures,
run `RESEARCH_MODE=4 cargo test --locked` from the lab's prototype tree in the build environment.
It intentionally exits nonzero: four integration assertions fail and later targets do not run.
This is retained adverse evidence, not an accepted production test result.

## Private evidence boundary

The public kit needs no private workbook. Published raw records cover generated synthetic
fixtures only; `summary.json` also contains the authorized private case's aggregate statistics.
The private workbook and its per-process/raw records are not included.

An independently authorized private test can mount an external directory containing `input.ods`
read-only at `/private` and explicitly invoke `python3 /kit/runner.py private`. Its logs/results
are written to the lab's `private/` directory. Keep that directory and all derived data private.
The direct runner's `all` stage also requests this optional input; the public synthetic wrapper
deliberately exposes individual stages instead. Never put private data in the Docker build
context or public fixtures. Publish aggregate statistics only with the owner's authorization.
