#!/usr/bin/env bash
set -euo pipefail

full=false
skip_assets=false
output_directory=""

while (( $# > 0 )); do
    case "$1" in
        -Full|--full)
            full=true
            ;;
        -SkipAssets|--skip-assets)
            skip_assets=true
            ;;
        -*)
            printf 'Unknown option: %s\n' "$1" >&2
            exit 1
            ;;
        *)
            [[ -z $output_directory ]] || { printf 'Only one output directory may be specified.\n' >&2; exit 1; }
            output_directory=$1
            ;;
    esac
    shift
done

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
project_name=$(basename -- "$project_root")
output_directory=${output_directory:-$(dirname -- "$project_root")}
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
    if $skip_assets && [[ $relative_path == docs/assets/* ]]; then
        continue
    fi

    source_path="$project_root/$relative_path"
    [[ -f $source_path ]] || continue
    mkdir -p "$staging/$(dirname -- "$relative_path")"
    cp -- "$source_path" "$staging/$relative_path"
    ((count += 1))
done < <(git -c core.quotepath=false --git-dir="$temporary_git" --work-tree="$project_root" ls-files -z --others --exclude-standard --exclude=.git/)

if $full; then
    git_path="$project_root/.git"
    [[ -e $git_path ]] || { printf '%s\n' "-Full requested, but .git was not found in: $project_root" >&2; exit 1; }

    cp -a -- "$git_path" "$staging/.git"
    if [[ -d $staging/.git ]]; then
        git_count=$(find "$staging/.git" -type f | wc -l)
        ((count += git_count))
    else
        ((count += 1))
    fi
fi

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
