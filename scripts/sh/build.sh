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
dist_path="$project_root/dist"

write_checksum() {
    local name=$1
    local path="$dist_path/$name"
    local hash
    hash=$(sha256sum "$path" | awk '{print $1}')
    printf '%s *%s\n' "$hash" "$name" >"$path.sha256"
    printf 'SHA-256: %s  %s\n' "$hash" "$name"
}

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
    --specpath "$project_root/build/pyinstaller"
    --workpath "$project_root/build/pyinstaller/work"
    --distpath "$dist_path"
    --collect-submodules app.gcode.export
    --add-data "$project_root/pyproject.toml:."
)

if [[ "$console" == true ]]; then
    "$python" "${arguments[@]}" --name easy_gcode_plot_cli --console "$project_root/cli_main.py"
    write_checksum easy_gcode_plot_cli
    exit 0
fi

"$python" "${arguments[@]}" --name easy_gcode_plot --windowed "$project_root/main.py"
write_checksum easy_gcode_plot
"$python" "${arguments[@]}" --name easy_gcode_plot_cli --console "$project_root/cli_main.py"
write_checksum easy_gcode_plot_cli
