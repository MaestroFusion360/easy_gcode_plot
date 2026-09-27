#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../../.." && pwd)
cli="$project_root/dist/easy_gcode_plot_cli"
input_dir="$project_root/tests/fixtures/turning"
output_dir="${TMPDIR:-/tmp}/easy_gcode_plot/batch/turning"

if [[ ! -f $cli ]]; then
    printf 'CLI executable not found: %s\n' "$cli" >&2
    exit 1
fi

"$cli" batch "$input_dir" \
    --lang fanuc_turn \
    --encoding utf-8 \
    -o "$output_dir"