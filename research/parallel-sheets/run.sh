#!/bin/bash
set -euo pipefail
stage=${1:?stage: generate, timing, correctness, failures, probes, extra, or summary}
case "$stage" in
    generate|timing|correctness|failures) python3 /kit/runner.py "$stage" ;;
    probes) python3 /kit/controls.py ;;
    extra) python3 /kit/extra.py ;;
    summary) python3 /kit/summary.py ;;
    *) echo "Unknown synthetic stage: $stage" >&2; exit 2 ;;
esac
