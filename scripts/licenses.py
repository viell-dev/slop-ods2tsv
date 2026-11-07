"""Collect dependency license texts for a target from the locked, filtered Cargo graph."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = {"MIT", "Apache-2.0", "Unicode-3.0", "Unlicense", "BSD-3-Clause", "BSD-2-Clause", "0BSD", "ISC", "Zlib", "BSL-1.0"}


def notices(target):
    data = json.loads(subprocess.check_output(["cargo", "metadata", "--locked", "--format-version", "1", "--filter-platform", target], cwd=ROOT, text=True))
    packages = {package["id"]: package for package in data["packages"]}
    nodes = {node["id"]: node for node in data["resolve"]["nodes"]}
    root = data["resolve"]["root"]
    pending = [root]
    selected = set()
    while pending:
        package = pending.pop()
        if package in selected:
            continue
        selected.add(package)
        pending.extend(dep["pkg"] for dep in nodes[package]["deps"] if any(kind["kind"] in (None, "build") for kind in dep["dep_kinds"]))
    result = ["Third-party notices for this target's locked normal/build dependency graph.\n"]
    for package in sorted((packages[key] for key in selected if key != root), key=lambda package: (package["name"], package["version"])):
        expression = package.get("license") or ""
        terms = set(re.findall(r'[A-Za-z0-9.+-]+', expression)) - {"OR", "AND"}
        assert terms and terms <= ALLOWED, f"Dependency license needs review: {package['name']}: {expression}"
        base = Path(package["manifest_path"]).parent.resolve()
        files = {path for path in base.iterdir() if path.is_file() and re.match(r'(?i)^(license|licence|copying|notice|unlicense)([._-]|$)', path.name)}
        if package.get("license_file"):
            files.add(base / package["license_file"])
        assert files, f"No license text found for {package['name']} {package['version']}"
        result.append(f"\n{'=' * 72}\n{package['name']} {package['version']}\nDeclared license: {expression}\n")
        for path in sorted(files):
            assert path.resolve().is_relative_to(base), "License path escapes package"
            result.append(f"\n--- {path.name} ---\n{path.read_text(encoding='utf-8')}\n")
    return "".join(result)


def runtime_files(target):
    """Include the pinned compiler's standard-library inventory and linked target runtime notices."""
    compiler = subprocess.check_output(["rustc", "--version"], cwd=ROOT, text=True).strip()
    pinned = tomllib.loads((ROOT / "rust-toolchain.toml").read_text(encoding="utf-8"))["toolchain"]["channel"]
    assert compiler.startswith(f"rustc {pinned} "), f"Unexpected compiler: {compiler}"
    sysroot = Path(subprocess.check_output(["rustc", "--print", "sysroot"], cwd=ROOT, text=True).strip())
    documentation = sysroot / "share/doc/rust"
    copyright = documentation / "COPYRIGHT-library.html"
    assert copyright.is_file(), "Pinned Rust standard-library copyright inventory is required"
    files = [("licenses/rust/COPYRIGHT-library.html", copyright)]
    license_directory = documentation / "licenses"
    assert (license_directory / "MIT.txt").is_file() and (license_directory / "Apache-2.0.txt").is_file()
    files.extend((f"licenses/rust/licenses/{path.name}", path) for path in sorted(license_directory.iterdir()) if path.is_file())
    files.append(("licenses/README.md", ROOT / "licenses/README.md"))
    if target == "x86_64-unknown-linux-musl":
        assert pinned == "1.99.1", "Review bundled musl version/notices when updating Rust"
        files.append(("licenses/musl-1.2.5.COPYRIGHT", ROOT / "licenses/musl-1.2.5.COPYRIGHT"))
    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(notices(args.target), encoding="utf-8", newline="\n")
