"""Build a standalone release ZIP with the repository's pinned Rust toolchain."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tomllib
import zipfile
from licenses import notices

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=["x86_64-pc-windows-msvc", "x86_64-unknown-linux-musl"])
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))["package"]["version"]
    env = os.environ.copy()
    if args.target.endswith("msvc"):
        env["RUSTFLAGS"] = " ".join(filter(None, [env.get("RUSTFLAGS"), "-C target-feature=+crt-static"]))
    subprocess.run(["cargo", "build", "--release", "--locked", "--target", args.target], cwd=ROOT, env=env, check=True)
    binary_name = "ods2tsv.exe" if args.target.endswith("msvc") else "ods2tsv"
    binary = ROOT / "target" / args.target / "release" / binary_name
    actual = subprocess.check_output([str(binary), "--version"], text=True).strip()
    if actual != "ods2tsv " + version:
        raise RuntimeError(f"Binary version mismatch: {actual}")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    archive = dist / f"ods2tsv-{version}-{args.target}.zip"
    if archive.exists():
        raise FileExistsError(f"Refusing to replace {archive}; use a fresh dist directory")
    notice_path = dist / f"{args.target}-THIRD_PARTY_NOTICES.txt"
    notice_path.write_text(notices(args.target), encoding="utf-8", newline="\n")
    files = [(binary_name, binary), ("THIRD_PARTY_NOTICES.txt", notice_path)] + [(name, ROOT / name) for name in (
        "README.md", "COPYING.md", "CHANGELOG.md", "CONTRIBUTING.md", "RELEASING.md", "SECURITY.md",
        "docs/FORMAT.md", "manifest.schema.json", "examples/workbook.fods", "CODE_OF_CONDUCT.md", ".github/labels.json",
    )]
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as package:
        for name, path in files:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if path == binary else 0o100644) << 16
            package.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(archive)


if __name__ == "__main__":
    main()
