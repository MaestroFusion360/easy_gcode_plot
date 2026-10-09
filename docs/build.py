"""Assemble the bilingual static landing page from editable HTML fragments."""

import argparse
import re
from pathlib import Path

from comparison import render_comparison

ROOT = Path(__file__).resolve().parent
PAGES = (("en", ROOT / "index.html"), ("ru", ROOT / "ru" / "index.html"))
INCLUDE = re.compile(r"^[ \t]*<!-- include: ([a-z0-9/.-]+) -->\n", re.MULTILINE)


def render(path, parents=()):
    """Expand includes relative to their template, preserving the HTML text."""
    path = path.resolve()
    if path in parents:
        raise ValueError(f"Circular HTML include: {path}")
    source = path.read_text(encoding="utf-8")
    for language in ("en", "ru"):
        marker = f"<!-- comparison: {language} -->"
        if marker in source:
            source = source.replace(marker, render_comparison(language))
    return INCLUDE.sub(lambda match: render(path.parent / match[1], (*parents, path)), source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check generated pages without writing files")
    args = parser.parse_args()
    stale = []
    for language, output in PAGES:
        # Follow the repository's CRLF working-tree policy on every platform.
        content = render(ROOT / "src" / language / "index.html").replace("\n", "\r\n").encode("utf-8")
        if args.check:
            if not output.exists() or output.read_bytes() != content:
                stale.append(str(output.relative_to(ROOT)))
        else:
            output.write_bytes(content)
            print(f"Generated {output.relative_to(ROOT)}")
    if stale:
        parser.exit(1, f"Landing pages are out of date: {', '.join(stale)}. Run python docs/build.py.\n")
    if args.check:
        print("Landing pages are up to date")


if __name__ == "__main__":
    main()
