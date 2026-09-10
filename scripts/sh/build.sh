#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
console=false
skip_tests=false
for argument in "$@"; do
    case "$argument" in
        --console) console=true ;;
        --skip-tests) skip_tests=true ;;
        *) printf 'Unknown option: %s\n' "$argument" >&2; exit 2 ;;
    esac
done

cd "$project_root"
if [[ $skip_tests == false ]]; then
    "$script_dir/test.sh"
fi

arguments=(
    run --isolated --locked --no-dev --group build pyinstaller
    --noconfirm --clean --onefile --name easy_gcode_plot
    --icon "$project_root/logo.ico"
    --specpath "$project_root/build/pyinstaller"
    --workpath "$project_root/build/pyinstaller/work"
    --distpath "$project_root/dist"
    --add-data "$project_root/pyproject.toml:."
)
if [[ $console == true ]]; then
    arguments+=(--console)
else
    arguments+=(--windowed)
fi
arguments+=("$project_root/main.py")
exec uv "${arguments[@]}"
