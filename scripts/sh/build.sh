#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

console=false
skip_tests=false
refresh_build_environment=false

while (($#)); do
    case "$1" in
        --console)
            console=true
            shift
            ;;
        --skip-tests)
            skip_tests=true
            shift
            ;;
        --refresh-build-environment)
            refresh_build_environment=true
            shift
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            exit 2
            ;;
    esac
done

build_environment="$project_root/.venv-build"
python="$build_environment/bin/python"

cd "$project_root"

if [[ "$skip_tests" == false ]]; then
    bash "$script_dir/test.sh"
fi

native_arguments=(--build-environment "$build_environment")
if [[ "$refresh_build_environment" == true ]]; then
    native_arguments+=(--refresh)
fi

bash "$script_dir/build-native.sh" "${native_arguments[@]}"

if [[ ! -x "$python" ]]; then
    printf 'Build Python is missing: %s\n' "$python" >&2
    exit 1
fi

if ! "$python" -c 'import PyInstaller' >/dev/null 2>&1; then
    printf 'PyInstaller module is missing from build environment: %s\n' "$build_environment" >&2
    exit 1
fi

arguments=(
    -m PyInstaller
    --noconfirm
    --clean
    --onefile
    --name easy_gcode_plot
    --icon "$project_root/logo.ico"
    --specpath "$project_root/build/pyinstaller"
    --workpath "$project_root/build/pyinstaller/work"
    --distpath "$project_root/dist"
    --collect-submodules app.gcode.export
    --add-data "$project_root/pyproject.toml:."
)

if [[ "$console" == true ]]; then
    arguments+=(--console)
else
    arguments+=(--windowed)
fi

arguments+=("$project_root/main.py")

exec "$python" "${arguments[@]}"
