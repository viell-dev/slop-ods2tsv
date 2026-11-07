# Agent maintenance

Keep the public README, CLI help, manifest schema, examples, contributor guidance, and release
instructions consistent with the implementation. User-facing Markdown describes the latest
installable release; identify unreleased behavior explicitly. No documentation site is required
for the current CLI scope.

Work through issues and pull requests on task branches from `main`. Use GitHub rebase merges for
linear history. Do not bypass required checks or main-branch protection. Use the shared labels in
`.github/labels.json`: one `Type:` and at most one `Status:` label per issue or PR. `Needs:` labels
are for a person who must act, with a self-contained request and that person's assignment.

The prototypes are public references, not this repository's runtime or verification infrastructure.
Keep all contributor and release procedures self-contained here. Preserve applicable licensing and
provenance when adapting their tests or code. Use synthetic inputs rather than private workbooks.

Record findings, their disposition, commands, platforms, and evidence limits in issues and PRs.
Perform a deliberate author review after checks pass. Give release PRs an independent agent review
of the coherent change and verify material fixes. A successful compile does not establish that a
release artifact runs on its target operating system.

Never replace published release bytes or move a released tag. A first alpha may be published after
its automated and independent checks; stable publication additionally requires an agreed goal and
a person's reported installation and use of a representative candidate. The maintainer owns
engineering and release work; this is not a requirement for human code review.
