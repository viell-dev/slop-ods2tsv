#!/bin/bash
set -euo pipefail
# Only a fresh disposable /lab is used; /kit and the product checkout stay read-only.
test -f /lab/source-beta1.tar
test ! -e /lab/base
test ! -e /lab/proto
export CARGO_HOME=/lab/cargo
mkdir -p "$CARGO_HOME/registry" /lab/base /lab/proto /lab/bin /lab/results
if test -d /cache; then cp -a /cache/. "$CARGO_HOME/registry/"; fi
tar -xf /lab/source-beta1.tar -C /lab/base
cp -a /lab/base/. /lab/proto/
patch --batch --directory=/lab/proto -p1 < /kit/prototype.patch
rustc -Vv > /lab/results/toolchain.txt
python3 -V >> /lab/results/toolchain.txt
cd /lab/base
cargo build --release --locked -j 6
cp target/release/ods2tsv /lab/bin/baseline
cd /lab/proto
cargo build --release --locked -j 6
cp target/release/ods2tsv /lab/bin/prototype
cargo fmt --check
cargo test --locked -j 6
