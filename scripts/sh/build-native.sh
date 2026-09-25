#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

build_environment="$project_root/.venv-build"
refresh=false

while (($#)); do
    case "$1" in
        --build-environment)
            if (($# < 2)); then
                printf 'Missing value for --build-environment\n' >&2
                exit 2
            fi
            build_environment=$2
            shift 2
            ;;
        --refresh)
            refresh=true
            shift
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            exit 2
            ;;
    esac
done

python="$build_environment/bin/python"
dependency_state_file="$build_environment/.easy-gcode-plot-dependencies-state"
native_state_file="$build_environment/.easy-gcode-plot-native-state"

dependency_inputs=(
    "$project_root/pyproject.toml"
    "$project_root/uv.lock"
)

native_inputs=(
    "$project_root/app/gcode/kernel/frontend/_native_parser.pyx"
    "$project_root/app/gcode/kernel/milling/_native_executor.pyx"
    "$project_root/app/tools/_native_discovery.pyx"
)

hash_file() {
    local path=$1

    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$path" | awk '{print $1}'
        return
    fi

    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$path" | awk '{print $1}'
        return
    fi

    printf 'Neither sha256sum nor shasum is available.\n' >&2
    exit 1
}

build_state() {
    local path
    local hash

    for path in "$@"; do
        if [[ ! -f "$path" ]]; then
            printf 'Build input is missing: %s\n' "$path" >&2
            exit 1
        fi

        hash=$(hash_file "$path")
        printf '%s:%s\n' "$(basename -- "$path")" "$hash"
    done
}

read_state() {
    local path=$1
    if [[ -f "$path" ]]; then
        cat -- "$path"
    fi
}

write_state() {
    local path=$1
    local value=$2
    printf '%s' "$value" >"$path"
}

sync_build_environment() {
    local reinstall_project=$1
    local reinstall_pyinstaller=$2

    local arguments=(
        sync
        --locked
        --no-dev
        --group build
    )

    if [[ "$reinstall_project" == true ]]; then
        arguments+=(--reinstall-package easy-gcode-plot)
    fi

    if [[ "$reinstall_pyinstaller" == true ]]; then
        arguments+=(--reinstall-package pyinstaller)
    fi

    (
        export UV_PROJECT_ENVIRONMENT="$build_environment"
        unset VIRTUAL_ENV
        uv "${arguments[@]}"
    )
}

cd "$project_root"

dependency_state=$(build_state "${dependency_inputs[@]}")
native_state=$(build_state "${native_inputs[@]}")

saved_dependency_state=$(read_state "$dependency_state_file")
saved_native_state=$(read_state "$native_state_file")

needs_dependency_sync=$refresh
if [[ ! -x "$python" ]]; then
    needs_dependency_sync=true
fi
if [[ "$saved_dependency_state" != "$dependency_state" ]]; then
    needs_dependency_sync=true
fi

if [[ "$needs_dependency_sync" == true ]]; then
    printf 'Refreshing build dependencies...\n'
    sync_build_environment true false
elif [[ "$saved_native_state" != "$native_state" ]]; then
    printf 'Build dependencies are up to date; dependency sync skipped.\n'
    printf 'Native sources changed; rebuilding easy-gcode-plot only...\n'
    sync_build_environment true false
else
    printf 'Build dependencies are up to date; dependency sync skipped.\n'
    printf 'Native extensions are up to date; rebuild skipped.\n'
fi

# Repair PyInstaller only if the module is really absent. Normal builds never do this.
if ! "$python" -c 'import PyInstaller' >/dev/null 2>&1; then
    printf 'PyInstaller module is missing; repairing build environment once...\n'
    sync_build_environment false true
fi

if ! "$python" -c 'import PyInstaller' >/dev/null 2>&1; then
    printf 'PyInstaller module is unavailable in build environment: %s\n' "$build_environment" >&2
    exit 1
fi

"$python" - <<'PY'
import app.gcode.kernel.frontend._native_parser as parser
import app.gcode.kernel.milling._native_executor as executor
import app.tools._native_discovery as discovery

print("Native parser:   " + parser.__file__)
print("Native executor: " + executor.__file__)
print("Native discovery: " + discovery.__file__)
print("Native acceleration is ready.")
PY

write_state "$dependency_state_file" "$dependency_state"
write_state "$native_state_file" "$native_state"
