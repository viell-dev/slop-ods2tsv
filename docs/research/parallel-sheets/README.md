# Parallel sheet parsing: bounded research for issue #42

Kept because it records the measured benefit, costs and prototype failures of parallel sheet
parsing, with a frozen reproduction kit, so a future adoption decision need not repeat the
experiment.

> [!NOTE]
> Research authored by a delegated GPT-6.1 Sol via Codex agent and submitted on viell's behalf
> by the parent GPT-6.1 Sol via Codex agent. Viell has not reviewed this report. This is an
> experiment, not a production implementation or release decision.

**Recommendation: defer production adoption.** Sheet parsing can provide a useful end-to-end
improvement: the balanced 100-sheet case improved from **0.623 s to 0.240 s median (2.60×)** with
six workers. Four workers reached **0.276 s (2.26×)**. The same design regresses
single-sheet, skewed and very small-sheet cases, retains substantially more memory, and has
confirmed prototype compatibility failures. Preserve the current serial implementation and
release scope. A separately assigned implementation could be justified for substantial,
reasonably balanced multi-sheet inputs after the conditions below are addressed.

This investigates [issue #42](https://github.com/viell-dev/slop-ods2tsv/issues/42). It establishes
no new supported option, dependency, platform promise, stable goal or release blocker. No
production defect was established by this investigation; the failures described here belong to
the scratch prototype.

## Source, environment and method

The unchanged baseline is the beta.1/main Git archive at
[`e1807728d6e92b699cab0a859b29092da4946309`](https://github.com/viell-dev/slop-ods2tsv/tree/e1807728d6e92b699cab0a859b29092da4946309).
The product checkout was never edited or used as the experiment's build tree. Parent-owned RC and
stable metadata/branch work proceeded independently.

Both executables were built once with **Rust 1.99.1**, release optimization and the existing
thin LTO configuration, for **x86_64-unknown-linux-gnu**. This measures a Linux source build,
not a Windows or distributed musl artifact. The scratch tree adds explicit **Rayon 1.12.0** and
**quick-xml 0.42.0**, an internal research module, an environment-controlled export hook, and
bounded XML materialization. The original xml-rs 1.4.0 reader and ZIP 9.4.1 remain in use.
Exact source, lockfile, patch, build recipe and raw results are retained.

The host ran Linux 6.18.60 on an **i7-4930K, 6 physical / 12 logical CPUs**, with 15 GiB RAM.
About 13–14 GiB was available at setup; swap was unused. Each disposable container had a
**6-CPU quota and 3-GiB memory cap**, without CPU affinity or frequency locking. No other
containers were observed during the experiments. Host load was initially near zero and around
1–1.5 during later observations. Shared-host scheduling, turbo and filesystem effects remain
limitations; this was not a controlled dedicated benchmark machine.

Each timed child performs the **complete export**: process startup, package inspection,
ZIP read/decompression and CRC/EOF checks, optional materialization/indexing/validation, pool
creation, original sheet parsing, ordered TSV output, metadata and both manifests. Fixture
generation, comparison and output deletion occur outside the timer. Runs use the normal flush
contract, warm filesystem caches and fresh output directories; there is no fsync or cold-cache
claim. GNU time supplies converter CPU time and peak RSS; external monotonic time supplies
elapsed time. CPU values have 0.01-second resolution.

There is one warmup per variant, then three rotating-order measured rounds. The 5,000-sheet,
empty-tail, output-heavy and merged cases have five rounds. All warmups, outliers and variance
are retained: **392 timed exports, including 308 measured exports**. No timing gate or universal
worker threshold is inferred from these samples. Separate instrumentation is reported alongside
the unchanged executable because instrumentation/code layout itself can affect timing.

## What was compared

| Variant | Work performed |
| --- | --- |
| Serial | Unchanged full exporter, independently built from the archive |
| Serial + timers | Original synchronous read/emit/write path with phase measurements |
| Index + 1 | Full bounded XML read; XML-aware scan/index and non-sheet validation; same reader in one Rayon worker; ordered original writer |
| Index + 2/4/6 | Same indexing and reader as the one-worker control, using a fresh bounded pool per export |
| Writer overlap | One original serial parser and one ordered writer, with a capacity-one channel and joined producer |

The index uses `NsReader` XML events and byte positions, rather than raw table-string searches.
Each fragment includes its original ancestor start/end tags to retain inherited namespace
declarations and wrapper depth. The original reader validates/projects each fragment; a skeleton
retaining non-sheet content is checked separately by the original reader. Original-document
depth is checked during indexing. Non-UTF-8 bytes or a non-UTF-8 declaration fall back to the
original reader after materialization. This is deliberately incomplete compatibility work.

Indexed `par_iter().map(...).collect::<Vec<_>>()` runs parsing in parallel and retains source
order. Batches hold at most twice the worker count in active/completed `Sheet` results. Each
batch joins before the controller invokes the unchanged `Run::write` in order. Workers do not
write files. Consequently filename allocation, warnings, merge reservations, the exact shared
output counter and manifests retain their original coordinator. This is actual parallel parsing;
there is no mutex disguising a serial parser.

Rayon's [`par_bridge`](https://docs.rs/rayon/1.12.0/rayon/iter/trait.ParallelBridge.html)
synchronizes calls to `next()` and does not guarantee source order. Bridging completed sheets
from the present reader would leave its expensive parsing serial. The
[indexed iterator API](https://docs.rs/rayon/1.12.0/rayon/iter/trait.IndexedParallelIterator.html)
supports splitting known indexed input; the experiment uses indexed fragments and ordered
collection. Pool construction uses the verified
[`ThreadPoolBuilder` API](https://docs.rs/rayon/1.12.0/rayon/struct.ThreadPoolBuilder.html).

## Complete-export measurements

Seconds, medians. `1/2/4/6` include indexing and the respective worker count. Dense cases have
**exactly 120,000 ordinary cells and 20,000 row templates** each; sheet count changes their
distribution. The skewed case puts 109,080 cells in one sheet and 120 cells in each of 91 others.

| Workload | Serial | 1 | 2 | 4 | 6 | Writer overlap | Rounds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense, 1 sheet | 0.622 | 0.733 | 0.746 | 0.728 | 0.732 | 0.648 | 3 |
| Dense, 2 sheets | 0.622 | 0.726 | 0.432 | 0.432 | 0.437 | 0.642 | 3 |
| Dense, 4 sheets | 0.618 | 0.719 | 0.434 | 0.271 | 0.270 | 0.639 | 3 |
| Dense, 8 sheets | 0.600 | 0.726 | 0.435 | 0.274 | 0.264 | 0.633 | 3 |
| Dense, 16 sheets | 0.602 | 0.725 | 0.434 | 0.273 | 0.230 | 0.631 | 3 |
| Dense, 100 sheets | 0.623 | 0.726 | 0.446 | 0.276 | 0.240 | 0.644 | 3 |
| Dense, 1,000 sheets | 0.729 | 0.918 | 0.557 | 0.409 | 0.332 | 0.743 | 3 |
| Dense, 5,000 sheets | 0.890 | 1.124 | 1.586 | 1.162 | 0.993 | 0.778 | 5 |
| Skewed, 92 sheets | 0.627 | 0.738 | 0.711 | 0.705 | 0.702 | 0.670 | 3 |
| Empty/repeated tail, 1,000 sheets | 0.050 | 0.085 | 0.076 | 0.057 | 0.057 | 0.030 | 5 |
| Output-heavy, 8 sheets | 0.116 | 0.114 | 0.115 | 0.114 | 0.113 | 0.115 | 5 |
| Merged, 8 sheets | 0.010 | 0.014 | 0.013 | 0.012 | 0.012 | 0.011 | 5 |

![Complete-export timings and fixed-work scaling](./chart.svg)

The one-worker control is roughly **16–26% slower** on the dense cases. Therefore the multi-worker
improvement is not a disguised replacement of the sheet parser with quick-xml. Parallel work
overcomes an added serial indexing cost. More workers cannot help a single large sheet; the skewed
input likewise retains its long serial task. Batching tiny sheets adds scheduling/coordination work
and exposes substantial variance: the 5,000-sheet/two-worker runs span **0.682–1.800 s**, versus
serial **0.868–0.900 s**. The median converter CPU cost there is **2.51 CPU-s**, versus serial
**0.88 CPU-s**. Extra CPU work is observed; its exact scheduling/filesystem cause was not isolated.
The observations are retained as a prototype performance limit, not a production bug.

Writer overlap helps the empty/tiny-file microcases, including 0.050 to 0.030 s for empty tails,
but not the dense cases through 1,000 sheets or the output-heavy case. The output-heavy fixture expands compact repeats
into 1.92 million fields: instrumentation measures approximately 0.110 s writing and 0.0003 s
reading/parsing. Overlapping a negligible parser phase cannot materially improve that workload.
The approximately 10-ms merged case is too small for strong relative timing conclusions.

## Dense 100-sheet case: phases, CPU, memory and variation

This synthetic input distributes 120,000 cells over 100 sheets. Every timed result and all four
mode comparisons match the unchanged baseline.

| Variant | Median s | Min–max s | Median CPU-s | Median / max RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| Serial | 0.623 | 0.616–0.624 | 0.61 | 3.32 / 3.34 |
| Serial + timers | 0.629 | 0.611–0.635 | 0.62 | 3.71 / 3.78 |
| Index + 1 | 0.726 | 0.716–0.733 | 0.71 | 14.43 / 15.76 |
| Index + 2 | 0.446 | 0.438–0.448 | 0.76 | 15.56 / 15.97 |
| Index + 4 | 0.276 | 0.276–0.289 | 0.77 | 16.15 / 16.43 |
| Index + 6 | 0.240 | 0.212–0.241 | 0.76 | 16.67 / 16.89 |
| Writer overlap | 0.644 | 0.642–0.646 | 0.65 | 3.82 / 3.88 |

Instrumented serial spends a median **0.616 s** in reading/parsing and **0.009 s** in writing;
the former includes interleaved decompression. For index + six workers, median phases are
**0.007 s materialization**, **0.083 s indexing/non-sheet validation**, **0.0003 s pool
creation**, **0.131 s batch parsing**, **0.011 s writing** and **0.0002 s finish**. Phase
medians need not add exactly to the total median. The overlap `parse_s` field is pipeline wall
time including waits; it must not be added to its simultaneous writer time.

The index/workers use about **25% more CPU** than unchanged serial while reducing latency.
Six workers save only another 0.036 s beyond four in this case. Maximum RSS is approximately
**5×** serial, principally because the full XML is retained, with additional parsed sheets,
wrappers and buffers. This is a tradeoff, not a free improvement.

## Correctness evidence and exposed shortcuts

The successful suite performs **500 exact baseline comparisons**, representing 380 distinct
case/options/variant combinations and 120 repeated smoke comparisons. It covers 19 synthetic
cases, all five experimental execution variants, and all four
saved/raw × collapsed/preserved modes. TSV bytes, filenames, order, complete sheet metadata and
warnings match. Only the export timestamp is normalized in JSON and the text manifest.

Controls include inherited/default/rebound namespaces, Unicode, nested tables, CDATA and
comments containing fake table tags, UTF-16 LE/BE and Latin-1 fallback, exact depth 256 and
exact 64-MiB XML. **52 rejection runs** cover malformed/trailing XML, unknown entities inside
and outside sheets, DTDs, CRC corruption, excess depth, cell/field/merge/XML/output limits and
hostile cross-sheet repeated merge metadata. Each expected rejection returns failure and removes
the owned output directory. The existing unit controls additionally exercise exact encoded-byte
accounting, retained merge reservations and preservation of unrelated files.

These passes do **not** establish production equivalence:

| Prototype finding | Evidence and disposition |
| --- | --- |
| Character references in namespace URIs can silently omit sheets | Baseline succeeds with one sheet; indexed variants can report success with zero sheets. The scanner's namespace comparison does not normalize the declaration as the existing reader does, and it lacks a coverage check. High impact if shipped; confined to prototype. Retained [synthetic repro](./repros/probe-namespace-reference.fods). |
| Spreadsheet under an ignored annotation is indexed | Baseline ignores it; indexed variants later fail while parsing that fragment. Index selection needs the original reader's ignored-subtree/context rules. Retained [synthetic repro](./repros/probe-ignored-spreadsheet.fods). |
| Diagnostics/classification differ | The original suite passes all 40 tests with the hook disabled. With mode 4, 11 unit and 24 integration tests pass; four integration assertions fail: CRC `Error::Read` classification, original XML syntax position, depth-message wording, and intentional research stderr. Cargo stops before the remaining manifest target. These are retained failures, not waived checks. |
| Copied ancestor tags multiply memory and work | A single diagnostic with 400 empty sheets and a 128-KiB root attribute takes 0.015 s / 3.29 MiB serial versus 1.467 s / 55.82 MiB at one worker; six workers still take 0.351 s / 56.90 MiB. All outputs match. The XML is under 200 KiB. This is one observation, not a timing distribution. |

The scanner's raw `Reader` alternative would not resolve namespaces; the documented
[`NsReader`](https://docs.rs/quick-xml/latest/quick_xml/reader/struct.NsReader.html) provides that
facility, but observed namespace-reference behavior still requires explicit handling in this design.
The [quick-xml configuration](https://docs.rs/quick-xml/0.42.0/quick_xml/reader/struct.Config.html)
states that `enable_all_checks` currently enables comment and end-name checks. It is not a
replacement for the existing whole-document contract, entity/DTD policy, depth and projection
limits. The [encoding
documentation](https://docs.rs/quick-xml/0.42.0/quick_xml/reader/struct.Reader.html) also requires
deliberate decoding for non-UTF-8 input; this experiment keeps the original-reader fallback rather
than introducing another decoder. ODF permits tables in several contexts, not only workbook sheets;
the [OASIS
schema](https://docs.oasis-open.org/office/OpenDocument/v1.3/os/part3-schema/OpenDocument-v1.3-os-part3-schema.html)
is another reason that lexical tag matching is insufficient.

## Production cost and conditions for revisiting

An implementation needs namespace normalization and full index coverage, the original ignored
context rules, original-depth checks, and mapped original line/column/error classifications. XML
outside sheets, trailing input, package CRC/EOF, DTD/entity restrictions and non-UTF-8 fallback must
remain real costs. A complete xml-rs prepass is a conservative alternative, but was not benchmarked
separately: the measured roughly 0.62-s serial reading/parsing phase of the 100-sheet case suggests
that adding such a pass before parallel parsing would erase its gain. That is an inference, not
another measured variant.

The prototype bounds pending sheet **count**, not decoded byte use. Retaining up to 64 MiB XML,
non-sheet validation buffers, per-fragment wrappers and multiple parsed sheets changes peak
memory substantially. Repeated values/merges and out-of-order completion need additional
consideration. Copying arbitrary ancestor tags for every sheet is unsuitable: store shared,
minimal namespace/context snapshots, and enforce a memory/backpressure strategy. Exact-XML
boundary controls reached approximately 149 MiB RSS in indexed execution; rejection controls
reached approximately 253 MiB. Existing input/output caps are not RAM ceilings.

Keep output ownership centralized unless a separately justified writer design preserves exact
combined-byte accounting, early merge-metadata reservations, deterministic portable names, warning
order and manifest order. The measured writer is too cheap in the dense cases to justify parallel
file emission. The prototype joins parse batches before write/abort; overlap drains and joins the
producer before cleanup. Production cancellation must retain that no-late-write property while
avoiding unnecessary parsing after failure, and needs explicit panic/resource-failure handling.
Batch barriers also cause head-of-line delay and tiny-task scheduling overhead.

Revisit after a scoped assignment defines acceptable memory/latency tradeoffs and demonstrates
correct adaptive selection on balanced, skewed, tiny-sheet and output-heavy cases. Four workers
are a reasonable next experimental default on this host; no universal default is established.
Investigating serial-reader overhead is another option with fewer cross-sheet ownership changes,
but this work did not implement a replacement parser or establish its speed. Do not infer its
benefit from quick-xml indexing speed alone. The simpler writer overlap is not a priority for
the measured dense workloads; its benefit is confined to small absolute costs in these tests.

## Retained artifacts and cleanup

Before publication, the parent recomputed the aggregate medians from all retained timing records,
checked the comparison/rejection counts. The actual Windows `0.1.0` release keeps one sheet in each
baseline repro. An independent rerun of the public kit in local Linux Docker built both locked
release binaries, passed formatting and all 40 normal tests, generated the synthetic fixtures, and
matched 100 additional four-mode text/namespace/encoding comparisons. It also reproduced both
indexed namespace/context gaps against the successful unchanged baseline. These are
kit/compatibility checks, not additional timing samples or an independent agent review.

[Reproduction instructions](./REPRODUCE.md) explain the disposable build, fixed fixtures and
commands. The [complete source patch](./prototype.patch) includes exact lockfile changes against
the public baseline commit. [Raw synthetic timings](./results/measurements.jsonl),
[aggregate statistics](./results/summary.json), [correctness records](./results/correctness.jsonl),
[rejection records](./results/failures.jsonl), [exploratory probes](./results/probes.jsonl) and
[failed prototype-suite evidence](./results/prototype-suite-mode4.log) are retained here.
Fixtures are independently generated; their original
inventory is retained in [fixtures.json](./results/fixtures.json). Regeneration preserves XML
work/content but ZIP generation timestamps can change archive hashes. The convenience rerun
container is documented separately from the original measured environment.

The disposable experiment containers and the remote experiment directory were removed. Setup
also had an initial interrupted `/tmp` attempt and two corrected runner setup errors.
No production files, releases, Git state or GitHub content were changed
by this research.
