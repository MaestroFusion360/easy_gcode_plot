#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
test_path=${1:-tests}
if (( $# > 0 )); then
    shift
fi
arguments=(run)
if [[ -n ${VIRTUAL_ENV:-} ]]; then
    arguments+=(--active)
fi
arguments+=(pytest "$test_path" "$@")

cd "$project_root"
exec uv "${arguments[@]}"
