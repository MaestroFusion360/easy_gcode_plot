#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../../.." && pwd)
cd "$project_root"

exec ./dist/easy_gcode_plot_cli batch-export tests/fixtures/milling/fanuc \
    --lang fanuc_mill \
    --mode expanded \
    --post-profile app/gcode/export/posts/sinumerik_840d.json \
    -o tmp/test_export/fanuc_mill_to_sinumerik_native
