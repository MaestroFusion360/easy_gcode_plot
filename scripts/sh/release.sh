#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
if (( $# < 2 || $# > 3 )); then
    printf 'Usage: %s VERSION MESSAGE [--push]\n' "$0" >&2
    exit 2
fi
version=$1
message=$2
push=false
if (( $# == 3 )); then
    [[ $3 == --push ]] || { printf 'Unknown option: %s\n' "$3" >&2; exit 2; }
    push=true
fi
tag="v$version"

cd "$project_root"
[[ -d .git ]] || { printf 'Run this script inside the repository.\n' >&2; exit 1; }
project_version=$(uv version --short)
[[ $project_version == "$version" ]] || {
    printf 'Requested release %s does not match pyproject version %s.\n' "$version" "$project_version" >&2
    exit 1
}
"$script_dir/lint.sh" --fix
"$script_dir/test.sh"
git diff --check
git status --short
if git ls-remote --exit-code --tags origin "refs/tags/$tag" >/dev/null 2>&1; then
    printf 'Tag %s already exists on origin.\n' "$tag" >&2
    exit 1
fi
if git rev-parse --verify --quiet "refs/tags/$tag" >/dev/null; then
    git tag -d "$tag"
fi
git add .
git diff --cached --quiet && { printf 'There are no staged changes to commit.\n' >&2; exit 1; }
git commit -m "$message"
git tag -a "$tag" -m "Release $version"
if [[ $push == true ]]; then
    git push
    git push origin "$tag"
else
    printf 'Release commit and tag created locally.\n'
fi
