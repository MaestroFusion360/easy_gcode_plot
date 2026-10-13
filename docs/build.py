"""Assemble the bilingual static landing page from editable HTML fragments."""

import argparse
import re
import tomllib
from html import escape
from pathlib import Path

from comparison import render_comparison

ROOT = Path(__file__).resolve().parent
PAGES = (("en", ROOT / "index.html"), ("ru", ROOT / "ru" / "index.html"))

INCLUDE = re.compile(
    r"^[ \t]*<!-- include: ([a-z0-9/.-]+) -->\n",
    re.MULTILINE,
)

BODY_END = re.compile(r"</body\s*>", re.IGNORECASE)

CLOUDFLARE_ANALYTICS = """<!-- Cloudflare Web Analytics -->
<script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "86f875da5419414b9da16320619c874e"}'></script>
<!-- End Cloudflare Web Analytics -->"""


def render(path, parents=(), *, version):
    """Expand includes relative to their template, preserving the HTML text."""
    path = path.resolve()

    if path in parents:
        raise ValueError(f"Circular HTML include: {path}")

    source = path.read_text(encoding="utf-8")
    source = source.replace("{{APP_VERSION}}", escape(version, quote=True))

    for language in ("en", "ru"):
        marker = f"<!-- comparison: {language} -->"
        if marker in source:
            source = source.replace(marker, render_comparison(language))

    return INCLUDE.sub(
        lambda match: render(path.parent / match[1], (*parents, path), version=version),
        source,
    )


def inject_analytics(html):
    """Insert Cloudflare Web Analytics before the closing body tag."""
    if CLOUDFLARE_ANALYTICS in html:
        return html

    if "static.cloudflareinsights.com/beacon.min.js" in html:
        raise ValueError(
            "Cloudflare Web Analytics already exists with different markup"
        )

    match = BODY_END.search(html)
    if match is None:
        raise ValueError("Missing </body> tag in landing page")

    return (
        html[:match.start()]
        + CLOUDFLARE_ANALYTICS
        + "\n"
        + html[match.start():]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check generated pages without writing files",
    )
    args = parser.parse_args()

    with (ROOT.parent / "pyproject.toml").open("rb") as project_file:
        version = tomllib.load(project_file)["project"]["version"]

    stale = []

    for language, output in PAGES:
        source = ROOT / "src" / language / "index.html"

        html = render(source, version=version)
        html = inject_analytics(html)

        # Follow the repository's CRLF working-tree policy on every platform.
        content = (
            html.replace("\r\n", "\n")
            .replace("\n", "\r\n")
            .encode("utf-8")
        )

        if args.check:
            if not output.exists() or output.read_bytes() != content:
                stale.append(str(output.relative_to(ROOT)))
        else:
            output.write_bytes(content)
            print(f"Generated {output.relative_to(ROOT)}")

    if stale:
        parser.exit(
            1,
            f"Landing pages are out of date: {', '.join(stale)}. "
            "Run python docs/build.py.\n",
        )

    if args.check:
        print("Landing pages are up to date")


if __name__ == "__main__":
    main()
