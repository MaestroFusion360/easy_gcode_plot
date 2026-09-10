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
source_file="$project_root/app/resources/files_res.qrc"
resource_dir=$(dirname -- "$source_file")
output_directory=${output_directory:-$resource_dir}
mkdir -p "$output_directory"
output_directory=$(CDPATH= cd -- "$output_directory" && pwd)
generated=$(mktemp "$output_directory/.rcc-XXXXXX.tmp")
normalized=$(mktemp "$output_directory/.rcc-normalized-XXXXXX.tmp")
trap 'rm -f -- "$generated" "$normalized"' EXIT

uv run --directory "$tool_project_root" --locked --group dev python - "$source_file" <<'PY'
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

manifest = Path(sys.argv[1])
entries = [node.text for node in ET.parse(manifest).getroot().findall(".//file")]
if any(not entry for entry in entries):
    raise SystemExit(f"Empty Qt resource entry in {manifest}")
if len(entries) != len(set(entries)):
    raise SystemExit(f"Duplicate Qt resource entry in {manifest}")
for entry in entries:
    if not (manifest.parent / entry).is_file():
        raise SystemExit(f"Qt resource manifest references a missing file: {entry} ({manifest})")
PY
uv run --directory "$tool_project_root" --locked --group dev pyside6-rcc "$source_file" -o "$generated"
sed 's/^from PySide6\([ .]\)/from PyQt6\1/' "$generated" > "$normalized"
if grep -Eq '^[[:space:]]*(from|import)[[:space:]]+PySide6' "$normalized"; then
    printf 'Generated resource module still imports PySide6: %s\n' "$source_file" >&2
    exit 1
fi
mv -- "$normalized" "$output_directory/files_res.py"
printf 'Generated %s\n' "$output_directory/files_res.py"
