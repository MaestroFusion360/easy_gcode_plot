#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
tool_project_root=$project_root
while (( $# > 0 )); do
    case "$1" in
        --project-root) project_root=$2; shift 2 ;;
        --tool-project-root) tool_project_root=$2; shift 2 ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
    esac
done
project_root=$(CDPATH= cd -- "$project_root" && pwd)
tool_project_root=$(CDPATH= cd -- "$tool_project_root" && pwd)
staging_root=$(mktemp -d "${TMPDIR:-/tmp}/easy-gcode-plot-qt-XXXXXX")
trap 'rm -rf -- "$staging_root"' EXIT
mkdir -p "$staging_root/ui" "$staging_root/resources"

"$script_dir/generate-resources.sh" --project-root "$project_root" --output-directory "$staging_root/resources" --tool-project-root "$tool_project_root"
"$script_dir/generate-ui.sh" --project-root "$project_root" --output-directory "$staging_root/ui" --tool-project-root "$tool_project_root"

shopt -s nullglob
for ui_file in "$project_root"/app/ui/generated/*.ui; do
    base_name=$(basename -- "$ui_file" .ui)
    target_name=$base_name.py
    if [[ $base_name == main_window ]]; then
        target_name=main_ui.py
    fi
    [[ -f "$staging_root/ui/$target_name" ]] || { printf 'Missing staged UI output: %s\n' "$target_name" >&2; exit 1; }
done
cp -- "$staging_root/resources/files_res.py" "$project_root/app/resources/files_res.py"
cp -- "$staging_root/ui/"*.py "$project_root/app/ui/generated/"
printf 'All Qt generated modules are up to date.\n'
