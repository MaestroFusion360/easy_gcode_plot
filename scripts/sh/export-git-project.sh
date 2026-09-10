#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
project_name=$(basename -- "$project_root")
output_directory=${1:-$(dirname -- "$project_root")}
mkdir -p "$output_directory"
output_directory=$(CDPATH= cd -- "$output_directory" && pwd)
timestamp=$(date '+%d-%m-%Y-%H-%M-%S')
archive_path="$output_directory/$project_name-$timestamp.zip"
[[ ! -e $archive_path ]] || { printf 'Archive already exists: %s\n' "$archive_path" >&2; exit 1; }
temporary_git=$(mktemp -d "${TMPDIR:-/tmp}/export-git-meta-XXXXXX")
staging=$(mktemp -d "${TMPDIR:-/tmp}/export-git-stage-XXXXXX")
trap 'rm -rf -- "$temporary_git" "$staging"' EXIT

git --git-dir="$temporary_git" --work-tree="$project_root" init --quiet
count=0
while IFS= read -r -d '' relative_path; do
    source_path="$project_root/$relative_path"
    [[ -f $source_path ]] || continue
    mkdir -p "$staging/$(dirname -- "$relative_path")"
    cp -- "$source_path" "$staging/$relative_path"
    ((count += 1))
done < <(git -c core.quotepath=false --git-dir="$temporary_git" --work-tree="$project_root" ls-files -z --others --exclude-standard --exclude=.git/)
(( count > 0 )) || { printf 'No files found to archive in: %s\n' "$project_root" >&2; exit 1; }
uv run python - "$staging" "$archive_path" <<'PY'
import sys
import zipfile
from pathlib import Path

source, target = map(Path, sys.argv[1:])
with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(source.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(source))
PY
printf 'Project : %s\nFiles   : %d\nZIP     : %s\n' "$project_root" "$count" "$archive_path"
