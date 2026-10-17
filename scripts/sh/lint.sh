#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
targets=(main.py cli_main.py app tests scripts/check_complexity.py scripts/analyze_gcode.py)
fix=false
check_resources=false
no_sync=false

for argument in "$@"; do
    case "$argument" in
        --fix) fix=true ;;
        --check-resources) check_resources=true ;;
        --no-sync) no_sync=true ;;
        *)
            printf 'Usage: %s [--fix] [--check-resources] [--no-sync]\n' "$0" >&2
            exit 2
            ;;
    esac
done

uv_run=(uv run)
if [[ "$no_sync" == true ]]; then
    uv_run+=(--no-sync)
    export UV_NO_SYNC=1
fi
if [[ -n ${VIRTUAL_ENV:-} ]]; then
    uv_run+=(--active)
fi

cd "$project_root"
if [[ "$fix" == true ]]; then
    "${uv_run[@]}" ruff format "${targets[@]}"
    "${uv_run[@]}" ruff check "${targets[@]}" --fix
    bash "$script_dir/generate-resources.sh" --project-root "$project_root"
else
    "${uv_run[@]}" ruff format --check "${targets[@]}"
    "${uv_run[@]}" ruff check "${targets[@]}"
fi
"${uv_run[@]}" python scripts/check_ui_format.py
qt_check_arguments=(python scripts/check_qt_sources.py)
if [[ "$check_resources" == true ]]; then
    qt_check_arguments+=(--check-resources)
fi
"${uv_run[@]}" "${qt_check_arguments[@]}"
"${uv_run[@]}" python scripts/check_complexity.py
"${uv_run[@]}" lint-imports --contract kernel-boundaries --no-logo --no-cache
exec "${uv_run[@]}" pylint "${targets[@]}"
