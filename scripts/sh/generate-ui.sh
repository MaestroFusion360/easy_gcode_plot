#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
default_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
project_root=$default_root
tool_project_root=$default_root
output_directory=
while (( $# > 0 )); do
    case "$1" in
        --project-root) project_root=$2; shift 2 ;;
        --tool-project-root) tool_project_root=$2; shift 2 ;;
        --output-directory) output_directory=$2; shift 2 ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
    esac
done
project_root=$(CDPATH= cd -- "$project_root" && pwd)
tool_project_root=$(CDPATH= cd -- "$tool_project_root" && pwd)
generated_dir="$project_root/app/ui/generated"
output_directory=${output_directory:-$generated_dir}
mkdir -p "$output_directory"
output_directory=$(CDPATH= cd -- "$output_directory" && pwd)
shopt -s nullglob
ui_files=("$generated_dir"/*.ui)
if (( ${#ui_files[@]} == 0 )); then
    printf 'No Qt Designer .ui files found in %s\n' "$generated_dir" >&2
    exit 1
fi

for ui_file in "${ui_files[@]}"; do
    base_name=$(basename -- "$ui_file" .ui)
    target_name=$base_name.py
    if [[ $base_name == main_window ]]; then
        target_name=main_ui.py
    fi
    temporary=$(mktemp "$output_directory/.uic-XXXXXX.tmp")
    uv run --directory "$tool_project_root" --locked --group dev pyside6-uic "$ui_file" -o "$temporary"
    uv run --directory "$tool_project_root" --locked --group dev python - "$temporary" "$output_directory/$target_name" <<'PY'
import re
import sys
from pathlib import Path

source, target = map(Path, sys.argv[1:])
content = source.read_text(encoding="utf-8")
content = re.sub(r"(?m)^from PySide6(?=[ .])", "from PyQt6", content)
aliases = {
    "Qt.Horizontal": "Qt.Orientation.Horizontal",
    "Qt.Vertical": "Qt.Orientation.Vertical",
    "QDialogButtonBox.Ok": "QDialogButtonBox.StandardButton.Ok",
    "QDialogButtonBox.Cancel": "QDialogButtonBox.StandardButton.Cancel",
}
for old, new in aliases.items():
    content = content.replace(old, new)
content = re.sub(r"(?m)^(?:from\s+\S+\s+import\s+files_res_rc|import\s+files_res_rc)\r?\n", "", content)
if ":/resource/" in content and "import app.resources.files_res" not in content:
    content = re.sub(
        r"(?m)^class Ui_",
        "import app.resources.files_res  # noqa: F401  # Registers Qt resources on import.\n\nclass Ui_",
        content,
        count=1,
    )
if re.search(r"(?m)^\s*(?:from|import)\s+PySide6", content):
    raise SystemExit(f"Generated UI module still imports PySide6: {source}")
target.write_text(content.rstrip("\r\n") + "\n", encoding="utf-8")
PY
    rm -f -- "$temporary"
    printf 'Generated %s\n' "$output_directory/$target_name"
done
