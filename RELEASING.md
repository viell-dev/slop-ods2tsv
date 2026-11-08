# Releasing ODS2TSV

## Readiness

`Cargo.toml` owns the SemVer version, without a `v` prefix. Alpha/beta/RC versions are GitHub
prereleases. [The first stable goal](https://github.com/viell-dev/slop-ods2tsv/issues/21) is agreed.
It covers the existing Windows/Linux portable CLI: ODS/FODS saved-value extraction, the documented
grid/text contract, ordered overview/JSON metadata, bounded failure handling and verified archives.
The [human usability request](https://github.com/viell-dev/slop-ods2tsv/issues/22) is complete:
alpha.3 natural use and focused alpha.5 presentation feedback, with its concrete findings fixed.
Separate agent-run checks remain functional evidence and are not the person's report.
The RC.1 publisher/metadata update changes no extraction or interaction behavior, so those
human reports and the alpha.5 correctness-checked benchmarks remain representative. The tracker and
preparation PR retain scope, exact commit, checks/results, benchmark method, platform evidence,
review findings and remaining limits.
Each version's changelog entry links its own tracker; that entry becomes its release notes.

Every release PR gets independent agent review of all changes since the previous release, plus
author review after checks pass. Record the reviewed revision and verify material fixes. Required
checks must pass on the final commit; never change protection to merge failing work.

Beta means the agreed features are complete and known findings are fixed or dispositioned. RC is
the exact intended stable candidate. Stable requires that candidate's engineering/platform evidence
and representative human usability evidence with no unresolved release blocker. Reassess evidence
after material changes. The [non-reproduced timing observation](https://github.com/viell-dev/slop-ods2tsv/issues/26)
and [unsigned-device policy investigation](https://github.com/viell-dev/slop-ods2tsv/issues/28) retain
their results and limits; neither is silently described as a performance or converter fix.

## Build and verify

Build on each target OS with the pinned compiler, native linker/SDK and Python 3.11+ development
requirements. Run only the applicable command:

```sh
python scripts/package.py --target x86_64-pc-windows-msvc
python scripts/package.py --target x86_64-unknown-linux-musl
```

Linux needs `musl-tools` and `rustup target add x86_64-unknown-linux-musl`; it can run in Docker
from Windows. Windows needs its C++/SDK toolchain. Release-only static CRT flags live in the build
child process, not global settings. ZIPs contain only the executable, rendered `docs/PORTABLE.txt`
as `README.txt`, application `LICENSE`, and the complete third-party/runtime notices. The portable
guide links to release-tagged reference/schema/examples; developer documents stay in the repository.
Preserve Linux executable permissions; each ZIP has a SHA-256 file. Archives are not overwritten:
start a new local build with a fresh `dist/`.

Include Cargo dependency texts, the pinned Rust standard-library inventory/license texts and target
runtime notices described in [licenses/README.md](licenses/README.md). Updating Rust requires review
of the linked musl version and notices; Cargo's graph does not describe the standard library.
Archives include the application's MIT `LICENSE` separately from all third-party notices. The owner
authorized MIT starting with alpha.4; preserve earlier tags/archives with their original notices.

Run `python scripts/artifact.py <ZIP>` on the target OS. It verifies hashes, contents, extraction
permissions and the installed executable's CLI/TSV/manifest corpus. Windows inspection rejects
non-system DLL imports and runs with only System32 on PATH. This runs on a hosted Windows runner,
not a pristine Windows installation; installed system files remain an evidence limit. Execute Linux
on a glibc distribution and Alpine without requiring Rust/Python in the runtime environment. Source
tests and cross-compiles do not replace artifact execution.

Run required interoperability checks and benchmarks with correctness assertions. Retain exact
archives, receipts, benchmark inputs/method/results and evidence limits. Docs/help/schema/version
checks must pass. Required real-file suites must fail when fixtures are absent.

## Publish and recover

After merging the checked preparation PR, dispatch the Release workflow from `main`. It defaults
to verification without publication. Publishing requires explicit input, a canonical stable or
alpha/beta/RC version, and successful CI for the exact main commit. Both target artifacts are built
and tested before a separate minimally privileged job creates the release with notes and checksums.
The [publisher](https://github.com/viell-dev/slop-ods2tsv/issues/38) marks alpha/beta/RC as
prereleases and never Latest. Stable versions use the normal release channel and GitHub's automatic
Latest selection. Notes identify the correct channel. All branch/commit/CI/tag/archive/checksum
gates apply to either path; `python scripts/test_release.py` checks both paths and failure cases
without real Git/GitHub calls. A dry run writes eligibility output without publishing or notes.

Before stable promotion, record comparison with the chosen RC: converter source, dependencies,
toolchain and packaging scripts must be unchanged. Version/documentation metadata can identify the
final release; rebuild and verify those actual downloads rather than claiming RC byte identity.
Material changes need another RC. Record the agreed goal, representative human evidence and any
remaining finding dispositions in the stable preparation PR before dispatching publication.

After publication verify the tag's commit, download assets, compare hashes/file lists, and execute
the actual downloads on Windows and Linux. Record release links, run IDs and verification in the
tracker before closing it. User release notes explain behavior, installation, compatibility and
limits without implying owner code review.

Never replace published bytes, move a release tag, or reuse a version. A dry run leaves publication
state unchanged. For partial publication, inspect existing state, then add only missing assets
whose hashes match checked artifacts for that same commit; use no overwrite flag. If bytes need
replacing, publish a new appropriate prerelease and explain supersession. Irreversible settings need
express owner approval; this procedure does not enable immutable releases.

## Human gate before stable

Before leaving alpha, agree the stable goal with the owner in an assigned `Needs: Owner` issue.
Beta means that goal's features are complete; RC is the exact intended stable candidate. Before
first stable, including pre-1.0 stable, a person must install and use a representative candidate
and report whether commands, feedback, output and recovery are understandable and usable. Repeat
after substantial interface or main-workflow changes. Routine fixes can reuse representative
recorded evidence with an explained assessment.

Prepare a direct candidate download, optional synthetic inputs and short tasks with expected outcomes.
Agents own scripted functional checks. Accept a person's natural-use observations without requiring
them to follow a regression script; distinguish their usability feedback from agent-run evidence.
Open a self-contained `Needs: Human` request assigned to the tester, or the owner to arrange one,
naming the stable release it blocks. Link it from the tracker and PR. Record the person's actual
report separately from maintainer dispositions. Keep it open until required coverage and resulting
work are complete; merging preparation must not close it. Missing/partial feedback leaves uncovered
scope pending. Automated execution, screenshots and agent review cannot satisfy this gate.

A prerelease may enable testing after engineering checks pass; it does not establish stable readiness.
ZIPs remain the baseline. `.deb`, other Linux packages, AppImage, repository submissions and installer
URLs are examples of possible proposals, not promised eventual goals. Weigh each actual addition
against project scope, benefit and ongoing maintenance/support cost before acceptance.
