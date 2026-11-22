#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
test_path=tests
path_set=false
no_sync=false
verbose=false
workers=4
pytest_arguments=()
while (( $# > 0 )); do
    case "$1" in
        --no-sync) no_sync=true ;;
        --verbose) verbose=true ;;
        --workers)
            if [[ $# -lt 2 ]]; then
                printf '%s\n' '--workers needs a value' >&2
                exit 2
            fi
            workers=$2
            shift
            ;;
        --workers=*) workers=${1#*=} ;;
        --help)
            printf 'Usage: %s [--no-sync] [--verbose] [--workers N] [path] [pytest arguments...]\n' "$0"
            exit 0
            ;;
        --)
            shift
            pytest_arguments+=("$@")
            break
            ;;
        -*)
            pytest_arguments+=("$@")
            break
            ;;
        *)
            if [[ "$path_set" == true ]]; then
                pytest_arguments+=("$@")
                break
            fi
            test_path=$1
            path_set=true
            ;;
    esac
    shift
done
if ! [[ "$workers" =~ ^[0-9]+$ ]] || (( workers > 64 )); then
    printf '%s\n' "Invalid --workers value: $workers" >&2
    exit 2
fi

arguments=(run)
if [[ "$no_sync" == true ]]; then
    arguments+=(--no-sync)
fi
if [[ -n ${VIRTUAL_ENV:-} ]]; then
    arguments+=(--active)
fi
arguments+=(pytest -q "$test_path")
if (( workers > 0 )); then
    # Whole files stay on one worker: module-scoped Qt fixtures and the qt-codegen
    # subprocess tests must not interleave with other workers.
    arguments+=(-n "$workers" --dist loadfile)
fi
arguments+=("${pytest_arguments[@]}")
if [[ "$verbose" == true ]]; then
    arguments+=(-v)
fi

cd "$project_root"
exec uv "${arguments[@]}"
