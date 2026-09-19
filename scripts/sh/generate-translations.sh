#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
default_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
project_root=$default_root
tool_project_root=$default_root
while (( $# > 0 )); do
    case "$1" in
        --project-root) project_root=$2; shift 2 ;;
        --tool-project-root) tool_project_root=$2; shift 2 ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
    esac
done
project_root=$(CDPATH= cd -- "$project_root" && pwd)
tool_project_root=$(CDPATH= cd -- "$tool_project_root" && pwd)
translations_dir="$project_root/translations"
output_dir="$project_root/app/resources/translations"
mkdir -p "$translations_dir" "$output_dir"

shopt -s nullglob
ts_files=("$translations_dir"/*.ts)
if (( ${#ts_files[@]} == 0 )); then
    printf 'No .ts translation sources found in %s; skipping translation generation.\n' "$translations_dir"
    exit 0
fi

sources=()
generated_ui_dir="$project_root/app/ui/generated"
if [[ -d $generated_ui_dir ]]; then
    while IFS= read -r -d '' file; do sources+=("$file"); done < <(
        find "$generated_ui_dir" -type f -name '*.ui' -print0 | LC_ALL=C sort -z
    )
fi
for relative_dir in app/ui/dialogs app/ui/windows app/ui/plot app/ui/support; do
    source_dir="$project_root/$relative_dir"
    if [[ -d $source_dir ]]; then
        while IFS= read -r -d '' file; do sources+=("$file"); done < <(
            find "$source_dir" -type f -name '*.py' -print0 | LC_ALL=C sort -z
        )
    fi
done
for relative_file in app/main_window.py app/application.py app/tools/definitions.py; do
    source_file="$project_root/$relative_file"
    [[ -f $source_file ]] && sources+=("$source_file")
done
if (( ${#sources[@]} == 0 )); then
    printf 'No translation sources found in %s; skipping translation generation.\n' "$project_root"
    exit 0
fi

uv run --directory "$tool_project_root" --locked --group dev pyside6-lupdate \
    "${sources[@]}" -extensions py -no-obsolete -ts "${ts_files[@]}"

for ts_file in "${ts_files[@]}"; do
    qm="$output_dir/$(basename -- "$ts_file" .ts).qm"
    uv run --directory "$tool_project_root" --locked --group dev pyside6-lrelease "$ts_file" -qm "$qm"
    printf 'Generated %s\n' "$qm"
done
