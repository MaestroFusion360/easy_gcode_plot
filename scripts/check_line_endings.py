"""Check/fix CRLF working-tree text, keeping shell scripts LF and binaries intact."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL_SHEBANG = re.compile(rb"^#![^\r\n]*\b(?:bash|sh)\b")
BINARY_CONTROLS = re.compile(rb"[\x00-\x08\x0b\x0e-\x1f\x7f]")


def repository_text_files(root: Path):
    """Use Git's file list and binary detection; ignore build/venv/tmp outputs."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "--eol", "-z"],
        check=True,
        capture_output=True,
    )
    seen = set()
    for entry in result.stdout.split(b"\0"):
        metadata, separator, name = entry.partition(b"\t")
        if not separator or b"attr/-text" in metadata or name in seen:
            continue
        seen.add(name)
        path = root / os.fsdecode(name)
        if path.is_file() and not path.is_symlink():
            # Git also labels plain text containing bare CR as binary.
            if b"w/-text" in metadata and re.search(rb"\r(?!\n)", path.read_bytes()) is None:
                continue
            yield path


def normalized_content(path: Path, content: bytes) -> bytes:
    """Change only newline bytes, preserving encoding, BOM and final-newline state."""
    if BINARY_CONTROLS.search(content):
        return content
    source = content.removeprefix(b"\xef\xbb\xbf")
    shell = path.suffix.lower() in {".sh", ".bash"} or SHELL_SHEBANG.match(source) is not None
    lf = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return lf if shell else lf.replace(b"\n", b"\r\n")


def check_repository(root: Path, *, fix: bool = False) -> int:
    checked = 0
    changed = []
    for path in repository_text_files(root):
        content = path.read_bytes()
        normalized = normalized_content(path, content)
        checked += 1
        if content != normalized:
            changed.append(path.relative_to(root))
            if fix:
                path.write_bytes(normalized)
    if changed and not fix:
        for path in changed[:20]:
            print(f"{path}: incorrect or mixed line endings")
        print(f"Line-ending check failed: {len(changed)} file(s). Run lint.ps1 -Fix.")
        return 1
    print(
        f"Line endings {'normalized' if fix else 'checked'}: {checked} text file(s), "
        f"{len(changed)} changed (CRLF; shell LF)."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args()
    try:
        return check_repository(args.root.resolve(), fix=args.fix)
    except (OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Cannot check line endings: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
