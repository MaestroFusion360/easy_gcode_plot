#!/usr/bin/env bash

set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

usage() {
    printf 'Usage: %s VERSION [MESSAGE] [--push]\n' "$0" >&2
}

if (( $# < 1 || $# > 3 )); then
    usage
    exit 2
fi

version=$1
shift

message=""
push=false

for arg in "$@"; do
    case "$arg" in
        --push)
            push=true
            ;;
        *)
            if [[ -n $message ]]; then
                printf 'Unexpected argument: %s\n' "$arg" >&2
                usage
                exit 2
            fi

            message=$arg
            ;;
    esac
done

tag="v$version"
tag_message="Release $version"

cd "$project_root"

[[ -d .git ]] || {
    printf 'Run this script from the repository root.\n' >&2
    exit 1
}

[[ -n $version ]] || {
    printf 'Version must not be empty.\n' >&2
    exit 1
}

printf '\n==> Verify project version\n'

project_version=$(uv version --short)

[[ $project_version == "$version" ]] || {
    printf \
        'Requested release %s does not match pyproject version %s.\n' \
        "$version" \
        "$project_version" >&2
    exit 1
}

printf '\n==> Lint / format\n'
bash "$script_dir/lint.sh" --fix --check-resources

printf '\n==> Tests\n'
bash "$script_dir/test.sh"

printf '\n==> git diff --check\n'
git diff --check

printf '\n==> Git status\n'
git status --short

printf '\n==> Check release tag\n'

if git ls-remote --exit-code --tags origin "refs/tags/$tag" >/dev/null 2>&1; then
    printf 'Tag %s already exists on origin. Refusing to overwrite it.\n' "$tag" >&2
    exit 1
fi

if git rev-parse --verify --quiet "refs/tags/$tag" >/dev/null; then
    printf 'Removing stale local tag %s.\n' "$tag"
    git tag -d "$tag"
fi

printf '\n==> Stage changes\n'
git add -A

if git diff --cached --quiet; then
    printf '\n==> No new changes to commit\n'
    printf 'Using current HEAD as the release commit.\n'

    release_commit=$(git rev-parse --short HEAD)
    release_message=$(git log -1 --pretty=%s)

    printf '\n'
    printf 'Version: %s\n' "$version"
    printf 'Commit:  %s\n' "$release_commit"
    printf 'Message: %s\n' "$release_message"
    printf 'Tag:     %s\n' "$tag"
else
    diff_exit=$?

    if (( diff_exit != 1 )); then
        printf 'Unable to determine staged changes (git diff exit code %d).\n' "$diff_exit" >&2
        exit 1
    fi

    if [[ -z $message ]]; then
        printf 'There are changes to commit, but no commit message was specified.\n' >&2
        exit 1
    fi

    printf '\n'
    printf 'Version:        %s\n' "$version"
    printf 'Commit message: %s\n' "$message"
    printf 'Tag:            %s\n' "$tag"

    printf '\n==> Create release commit\n'
    git commit -m "$message"

    release_commit=$(git rev-parse --short HEAD)
    release_message=$message
fi

printf '\n==> Create annotated tag %s\n' "$tag"
git tag -a "$tag" -m "$tag_message"

if [[ $push == true ]]; then
    printf '\n==> Push commit\n'
    git push

    printf '\n==> Push tag %s\n' "$tag"
    git push origin "$tag"
else
    printf '\nRelease commit and tag created locally.\n'
    printf 'To push them:\n'
    printf '  git push\n'
    printf '  git push origin %s\n' "$tag"
fi

printf '\nDone: %s (%s)\n' "$release_message" "$tag"
