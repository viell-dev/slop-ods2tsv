# Documentation maintenance

Use this checklist in each PR, recording the affected surfaces, commands/results and deliberate
prose/example review. The public default describes the newest published release. Mark pending
behavior as unreleased; use release-tagged references for installed versions. Historical evidence
belongs in issues, release records and the changelog rather than current operating instructions.

## Change checklist

| Change | Authoritative facts | Surfaces to review | Required evidence |
| --- | --- | --- | --- |
| CLI, options, defaults, limits | `src/main.rs`, `Options`/`ValueMode`, constants in `src/lib.rs` | README help/use/limits, FORMAT, PORTABLE, examples, rustdoc | Rust tests; `check.py` help/version/corpus; deliberate prose/example review |
| Extraction, warnings, completion, recovery | Reader/output implementation and explicit regression expectations | README, FORMAT, PORTABLE, examples, security limits, rustdoc | Regression tests; named corpus; real Calc check when affected; review exit codes and partial-output prose |
| Manifest or TSV contract | `src/manifest.rs`, output implementation, schema and FORMAT | JSON schema, README, PORTABLE, examples, public result rustdoc | Schema/corpus tests, exact TSV controls; assess additive versus incompatible schema changes |
| Version, channel, support | Cargo version; `release_metadata.py`; SECURITY support policy | Cargo.lock, schema `$id`, FORMAT version, README status, PORTABLE rendering, changelog, release notes | Normal and optimized Python suites; package/artifact checks; exact-main CI and actual downloads |
| Setup, checks, packaging | Toolchain, requirements, workflows and scripts | CONTRIBUTING, RELEASING, license inventory, this checklist | Follow platform commands; archive/import/license controls; record environment limits |

After changing CLI help, run `check.py --binary <executable> --write-help`, review the README diff,
then rerun without `--write-help`. Review behavioral prose even when help text is unchanged.
For version changes, keep the package version in Cargo.lock aligned without updating dependencies.
Never move a release tag or replace published bytes to correct documentation. Current-release prose
can be corrected on `main` through a checked PR without retagging; record its documentation commit
and clarify that installed guides retain their release's text.

## Check boundaries

`python -m unittest discover -s scripts -p 'test_*.py'` and the same command with `python -O`
exercise network-free channel, publication/failure, archive/license/import and link controls.
`check.py --binary <executable>` has separate metadata, corpus and Markdown functions. It checks
actual version/help, generated manifests against the schema, named extraction/recovery/stream
scenarios and maintained local Markdown links. `artifact.py` invokes that corpus once for a freshly
installed target archive, then checks imports and the shipped text example. Linux's Alpine and
Calc checks remain distinct environments and behaviors.

These checks do not prove arbitrary prose correct. Review TSV encoding/separators/record endings,
value fallbacks, whitespace examples, exit codes, support/channel claims, recovery instructions and
the complete unfamiliar-user path from download through reporting. Required PR evidence names the
reviewed revision and any platform, policy or manual-setup limits. Human usability evidence is
separate from agent-run functional checks.

The link inventory covers root Markdown and recursive `docs/`, `licenses/`, `research/` and
`.github/` Markdown, excluding generated `results/`, artifacts, targets, distributions, virtual
environments and symlink files. Inline links/images and reference definitions support local files,
same/cross-file heading fragments, percent-encoded targets, ATX/setext headings, duplicate heading
suffixes and explicit HTML `id`/anchor `name`. Fenced examples are excluded. External URLs are not
fetched. This is a bounded Markdown check: embedded HTML links, JavaScript-generated anchors and
non-Markdown fragments need manual review; unsupported non-Markdown fragments fail explicitly.

## Label maintenance

`.github/labels.json` owns Type, Status, Needs and contribution labels. `accessibility` is an
intentional extra dimension, not a competing classification. Inspect all open and closed issues
and PRs before changing labels so history keeps its classification:

```sh
gh api --paginate repos/viell-dev/slop-ods2tsv/labels
gh api --paginate 'repos/viell-dev/slop-ods2tsv/issues?state=all&per_page=100'
```

Compare names case-sensitively for display, plus colors and descriptions against the catalog.
Update existing catalog labels with `gh api --method PATCH .../labels/<encoded-name>` and a JSON
body containing `new_name`, `color` and `description`; create missing entries with POST to
`.../labels`. For a redundant label, migrate every use to the appropriate catalog Type/Status
before deleting it with DELETE. Classify actual scope rather than blindly adding a second Type.
Do not automatically map an ambiguous label such as `invalid`. Re-read labels and all issue/PR
classifications afterward, checking exactly one Type and at most one Status. Record intentional
extras and the comparison in the issue. No additional bot is needed.
