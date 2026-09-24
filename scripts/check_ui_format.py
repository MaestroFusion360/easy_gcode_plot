"""Check whitespace and XML syntax in Qt Designer source files."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def check_file(path: Path) -> list[str]:
    content = path.read_bytes()
    errors = []
    if not content.endswith(b"\n"):
        errors.append("missing final newline")
    try:
        source = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [*errors, f"invalid UTF-8: {exc}"]
    for number, line in enumerate(source.splitlines(), 1):
        if "\t" in line:
            errors.append(f"line {number}: tab character")
        if line.rstrip(" \t") != line:
            errors.append(f"line {number}: trailing whitespace")
    try:
        ET.fromstring(source)
    except ET.ParseError as exc:
        errors.append(f"invalid XML: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="UI files or directories")
    args = parser.parse_args()
    paths = args.paths or [Path("app/ui/generated")]
    files = sorted({file for path in paths for file in (path.rglob("*.ui") if path.is_dir() else [path])})
    if not files:
        parser.error("no UI files found")
    failures = 0
    for path in files:
        for error in check_file(path):
            print(f"{path}: {error}")
            failures += 1
    if failures:
        print(f"UI format check failed: {failures} issue(s) in {len(files)} file(s)")
        return 1
    print(f"UI format check passed: {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
