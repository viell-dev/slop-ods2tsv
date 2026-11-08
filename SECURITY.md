# Security reports

Report vulnerabilities privately through
[GitHub security advisories](https://github.com/viell-dev/slop-ods2tsv/security/advisories/new), with
version, platform, minimal synthetic reproducer and impact. Do not publish private workbooks,
credentials or exploit details in ordinary issues.

Fixes target the newest prerelease; older prereleases are not separately maintained. The tool reads
local ZIP/XML and creates a new export. It does not execute macros, calculate formulas, follow external
resources or decrypt content. Resource limits are not a promise that arbitrary hostile data is cheap.
The [fixed caps](README.md#scope-and-limits) include 256 open XML elements and 256 MiB of
combined TSV/manifest output per export. They reject excessive expansion with normal cleanup;
they are not a sandbox or a strict memory/time guarantee. Interruption and failed cleanup can
still leave partial files marked `.incomplete`. Use ordinary OS isolation for untrusted files.
