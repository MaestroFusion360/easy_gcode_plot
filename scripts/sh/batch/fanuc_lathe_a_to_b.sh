#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../../.." && pwd)
cd "$project_root"

exec ./dist/easy_gcode_plot_cli batch-export tests/fixtures/turning \
    --lang fanuc_turn \
    --lathe-gcode-system A \
    --mode expanded \
    --post-profile app/gcode/export/posts/fanuc_lathe_b.json \
    -o tmp/test_export/fanuc_lathe_a_to_b
