"""Render the authored comparison Markdown into the static landing pages.

Only the small Markdown subset used by COMPARISON*.md is accepted. No browser
fetch, Markdown dependency or separate copy of the comparison is required.
"""

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPOSITORY = "https://github.com/MaestroFusion360/easy_gcode_plot/blob/main/"
INLINE = re.compile(r"(`[^`]+`|\*\*.+?\*\*|\[[^\]]+\]\([^)]+\)|\[(?:U|E|C[1-6])\])")


def _link(target, language):
    if target.startswith("../"):
        return REPOSITORY + target[3:]
    if target.startswith("COMPARISON") and language == "ru":
        return "../" + target
    return target


def _inline(source, language):
    parts = []
    for index, value in enumerate(INLINE.split(source)):
        if index % 2 == 0:
            parts.append(html.escape(value))
        elif value.startswith("`"):
            parts.append(f"<code>{html.escape(value[1:-1])}</code>")
        elif value.startswith("**"):
            parts.append(f"<strong>{_inline(value[2:-2], language)}</strong>")
        elif "](" in value:
            label, target = value[1:-1].split("](", 1)
            parts.append(f'<a href="{html.escape(_link(target, language), quote=True)}">{html.escape(label)}</a>')
        else:
            parts.append(f'<span class="source-ref">{html.escape(value)}</span>')
    return "".join(parts)


def _blocks(source, language):
    output = []
    for block in source.strip().split("\n\n"):
        lines = block.splitlines()
        if not lines:
            continue
        if lines[0].startswith("| "):
            rows = [line.strip().strip("|").split("|") for line in lines]
            header = "".join(f'<th scope="col">{_inline(cell.strip(), language)}</th>' for cell in rows[0])
            body = []
            for row in rows[2:]:
                cells = "".join(f"<td>{_inline(cell.strip(), language)}</td>" for cell in row)
                body.append(f"<tr>{cells}</tr>")
            label = "Comparison table" if language == "en" else "Таблица сравнения"
            output.append(
                f'<div class="table-wrap" tabindex="0" role="region" aria-label="{label}">'
                f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
            )
        elif all(line.startswith("- ") for line in lines):
            output.append("<ul>" + "".join(f"<li>{_inline(line[2:], language)}</li>" for line in lines) + "</ul>")
        else:
            output.append(f"<p>{_inline(' '.join(lines), language)}</p>")
    return "\n".join(output)


def render_comparison(language):
    filename = "COMPARISON.md" if language == "en" else "COMPARISON_RU.md"
    text = (ROOT / filename).read_text(encoding="utf-8")
    intro, *sections = re.split(r"^## ", text, flags=re.MULTILINE)
    # The landing page supplies its own section heading.
    content = [_blocks(intro.split("\n", 1)[1], language)]
    for section in sections:
        title, body = section.split("\n", 1)
        content.append(
            f'<details class="reference-panel"><summary>{html.escape(title)}</summary>'
            f'<div class="reference-body">{_blocks(body, language)}</div></details>'
        )
    return "\n".join(content)
