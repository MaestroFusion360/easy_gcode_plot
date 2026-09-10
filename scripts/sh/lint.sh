#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
targets=(main.py app tests)
uv_run=(uv run)
if [[ -n ${VIRTUAL_ENV:-} ]]; then
    uv_run+=(--active)
fi

cd "$project_root"
if [[ ${1:-} == --fix ]]; then
    "${uv_run[@]}" ruff format "${targets[@]}"
    "${uv_run[@]}" ruff check "${targets[@]}" --fix
elif (( $# > 0 )); then
    printf 'Usage: %s [--fix]\n' "$0" >&2
    exit 2
else
    "${uv_run[@]}" ruff format --check "${targets[@]}"
    "${uv_run[@]}" ruff check "${targets[@]}"
fi
exec "${uv_run[@]}" pylint "${targets[@]}"
