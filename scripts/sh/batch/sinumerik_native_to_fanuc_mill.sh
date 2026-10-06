#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../../.." && pwd)
cd "$project_root"

exec ./dist/easy_gcode_plot_cli batch-export tests/fixtures/milling/sinumerik \
    --lang fanuc_mill \
    --mode expanded \
    --post-profile app/gcode/export/posts/fanuc_mill.json \
    -o tmp/test_export/sinumerik_native_to_fanuc_mill
