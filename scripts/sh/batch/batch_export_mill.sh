#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../../.." && pwd)
cli="$project_root/dist/easy_gcode_plot_cli"

if [[ ! -f $cli ]]; then
    printf 'CLI executable not found: %s\n' "$cli" >&2
    exit 1
fi

exec "$cli" batch-export "$project_root/tests/fixtures/milling" \
    --lang fanuc_mill --encoding utf-8 --format nc --mode expanded \
    --units auto --arc-type auto --no-sequence-numbers --spaces \
    --no-leading-zero --comments \
    -o "${TMPDIR:-/tmp}/easy_gcode_plot/batch_export/milling"
