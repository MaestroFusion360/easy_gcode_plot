#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
automated=false
delay_ms=1000

while (($#)); do
    case "$1" in
        --automated)
            automated=true
            shift
            ;;
        --delay-ms)
            if (($# < 2)) || [[ ! $2 =~ ^[0-9]{1,5}$ ]] || ((10#$2 > 60000)); then
                printf 'Expected --delay-ms NUMBER between 0 and 60000.\n' >&2
                exit 2
            fi
            delay_ms=$2
            shift 2
            ;;
        --help|-h)
            printf 'Usage: bash scripts/sh/start-sandbox.sh [--automated] [--delay-ms 1000]\n'
            printf 'Default: visible GUI demo. --automated: offscreen test without pauses.\n'
            exit 0
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            exit 2
            ;;
    esac
done

if [[ $automated == true ]]; then
    qt_platform=offscreen
    demo=0
else
    qt_platform=${QT_QPA_PLATFORM:-}
    case "$qt_platform" in
        ''|offscreen|minimal)
            case "$(uname -s)" in
                Darwin) qt_platform=cocoa ;;
                MINGW*|MSYS*|CYGWIN*) qt_platform=windows ;;
                *) qt_platform=xcb ;;
            esac
            ;;
    esac
    demo=1
fi

# Environment overrides belong only to the child test process.
QT_QPA_PLATFORM="$qt_platform" EASY_GCODE_SMOKE_DEMO="$demo" EASY_GCODE_SMOKE_DELAY_MS="$delay_ms" \
    exec bash "$script_dir/test.sh" tests/gui/test_daily_workflow_smoke.py -q -s
