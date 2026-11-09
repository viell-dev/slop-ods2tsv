# Security reports

Report vulnerabilities privately through
[GitHub security advisories](https://github.com/viell-dev/slop-ods2tsv/security/advisories/new), with
version, platform, minimal synthetic reproducer and impact. Do not publish private workbooks,
credentials or exploit details in ordinary issues.

## Supported versions

Security fixes target the newest stable release line (currently `0.1.x`); install its newest
published patch. Older stable lines and superseded patches are not maintained separately.
During active development of the next version, its newest alpha, beta or RC also receives relevant
fixes. A prerelease does not replace stable support, and older prereleases are not maintained.
See [releases](https://github.com/viell-dev/slop-ods2tsv/releases) for published versions. This is
the portable Windows/Linux CLI policy, without a long-term support channel.

## Input and execution limits

The tool reads
local ZIP/XML and creates a new export. It does not execute macros, calculate formulas, follow external
resources or decrypt content. Resource limits are not a promise that arbitrary hostile data is cheap.
The [fixed caps](README.md#scope-and-limits) include 256 open XML elements and 256 MiB of
combined TSV/manifest output per export. They reject excessive expansion with normal cleanup;
they are not a sandbox or a strict memory/time guarantee. Interruption and failed cleanup can
still leave partial files marked `.incomplete`. Use ordinary OS isolation for untrusted files.
