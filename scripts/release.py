"""Validate the exact main commit and publish only a verified, new prerelease version."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "viell-dev/slop-ods2tsv"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    assert os.environ.get("GITHUB_REF") == "refs/heads/main", "Release must run from main"
    version = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))["package"]["version"]
    assert re.fullmatch(r'\d+\.\d+\.\d+-(alpha|beta|rc)\.\d+', version), "Only explicit prereleases are currently supported"
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert sha == os.environ["GITHUB_SHA"]
    runs = json.loads(subprocess.check_output(["gh", "api", f"repos/{REPOSITORY}/actions/runs?head_sha={sha}&event=push"], text=True))
    assert any(run["name"] == "CI" and run["head_sha"] == sha and run["conclusion"] == "success" for run in runs["workflow_runs"]), "Exact main commit needs successful push CI"
    tags = subprocess.check_output(["git", "ls-remote", "--tags", "origin", f"refs/tags/{version}"], cwd=ROOT, text=True)
    assert not tags.strip(), "Tag already exists; inspect publication state instead of reusing it"
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write(f"version={version}\n")
    if not args.publish:
        print(f"Verified release eligibility: {version}, {sha}; no publication changes made.")
        return
    expected = {f"ods2tsv-{version}-{target}.zip" for target in ("x86_64-pc-windows-msvc", "x86_64-unknown-linux-musl")}
    archives = list((ROOT / "dist").glob("*.zip"))
    assert {path.name for path in archives} == expected, "Missing or unexpected platform artifacts"
    assets = []
    for archive in sorted(archives):
        checksum = archive.with_suffix(".zip.sha256")
        digest, name = checksum.read_text(encoding="utf-8").strip().split()
        assert name == archive.name and digest == hashlib.sha256(archive.read_bytes()).hexdigest()
        assets.extend([str(archive), str(checksum)])
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = re.search(rf'(?ms)^## {re.escape(version)}\n(.*?)(?=^## |\Z)', changelog)
    assert entry, "No changelog entry for this version"
    notes = ROOT / "dist/release-notes.md"
    notes.write_text(entry[1].strip() + f"\n\nDownload the ZIP and matching SHA-256 file for your platform. Extract and run; no language runtime is required. [Installation, commands and limits](https://github.com/{REPOSITORY}/blob/{version}/README.md).\n\nThis is an experimental prerelease, not a stable release. Formulas are not recalculated; content decryption is unsupported.\n", encoding="utf-8")
    subprocess.run(["gh", "release", "create", version, *assets, "--repo", REPOSITORY,
                    "--target", sha, "--title", version, "--prerelease", "--latest=false",
                    "--notes-file", str(notes)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
