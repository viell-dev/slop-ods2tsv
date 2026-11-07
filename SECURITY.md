# Security reports

Report vulnerabilities privately through
[GitHub security advisories](https://github.com/viell-dev/slop-ods2tsv/security/advisories/new), with
version, platform, minimal synthetic reproducer and impact. Do not publish private workbooks,
credentials or exploit details in ordinary issues.

Fixes target the newest alpha; older alphas are not separately maintained. The tool reads local
ZIP/XML and creates a new export. It does not execute macros, calculate formulas, follow external
resources or decrypt content. Resource limits are not a promise that arbitrary hostile data is cheap.
There is currently no total output-byte or XML-depth cap. Large repetitions and deeply nested XML
can consume substantial disk or CPU; [issue 9](https://github.com/viell-dev/slop-ods2tsv/issues/9)
tracks the measured limits and follow-up policy.
