# Releasing ODS2TSV

## Readiness

`Cargo.toml` owns the SemVer version, without a `v` prefix. Alpha/beta/RC versions are GitHub
prereleases. The initial version is `0.1.0-alpha.1`; a stable scope agreement and human usability
report are still required before stable. The tracker and preparation PR retain scope, exact commit,
checks/results, benchmark method, platform evidence, review findings and remaining limits.
Each version's changelog entry links its own tracker; that entry becomes its release notes.

Every release PR gets independent agent review of all changes since the previous release, plus
author review after checks pass. Record the reviewed revision and verify material fixes. Required
checks must pass on the final commit; never change protection to merge failing work.

## Build and verify

Build on each target OS with the pinned compiler, native linker/SDK and Python 3.11+ development
requirements. Run only the applicable command:

```sh
python scripts/package.py --target x86_64-pc-windows-msvc
python scripts/package.py --target x86_64-unknown-linux-musl
```

Linux needs `musl-tools` and `rustup target add x86_64-unknown-linux-musl`; it can run in Docker
from Windows. Windows needs its C++/SDK toolchain. Release-only static CRT flags live in the build
child process, not global settings. ZIPs contain the executable, public Markdown/schema/license
files, and Linux executable permissions; each has a SHA-256 file. Archives are not overwritten:
start a new local build with a fresh `dist/`.

Include Cargo dependency texts, the pinned Rust standard-library inventory/license texts and target
runtime notices described in [licenses/README.md](licenses/README.md). Updating Rust requires review
of the linked musl version and notices; Cargo's graph does not describe the standard library.

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
to verification without publication. Publishing requires explicit input, an alpha/beta/RC version,
and successful CI for the exact main commit. Both target artifacts are built and tested before a
separate minimally privileged job creates the prerelease with its notes and checksums.

After publication verify the tag's commit, download assets, compare hashes/file lists, and execute
the actual downloads on Windows and Linux. Record release links, run IDs and verification in the
tracker before closing it. User release notes explain behavior, installation, compatibility and
limits without implying owner code review.

Never replace published bytes, move a release tag, or reuse a version. A dry run leaves publication
state unchanged. For partial publication, inspect existing state, then add only missing assets
whose hashes match checked artifacts for that same commit; use no overwrite flag. If bytes need
replacing, publish a new alpha and explain supersession. Irreversible settings need express owner
approval; this procedure does not enable immutable releases.

## Human gate before stable

Before leaving alpha, agree the stable goal with the owner in an assigned `Needs: Owner` issue.
Beta means that goal's features are complete; RC is the exact intended stable candidate. Before
first stable, including pre-1.0 stable, a person must install and use a representative candidate
and report whether commands, feedback, output and recovery are understandable and usable. Repeat
after substantial interface or main-workflow changes. Routine fixes can reuse representative
recorded evidence with an explained assessment.

Prepare a direct candidate download, synthetic inputs, short numbered tasks and expected outcomes.
Open a self-contained `Needs: Human` request assigned to the tester, or the owner to arrange one,
naming the stable release it blocks. Link it from the tracker and PR. Record the person's actual
report separately from maintainer dispositions. Keep it open until required coverage and resulting
work are complete; merging preparation must not close it. Missing/partial feedback leaves uncovered
scope pending. Automated execution, screenshots and agent review cannot satisfy this gate.

An alpha may enable testing after engineering checks pass; it does not establish stable readiness.
ZIPs remain the baseline. Consider `.deb`, other Linux packages, AppImage, repository submissions
and installer URLs only near stable after sustained use; these are optional later decisions.
