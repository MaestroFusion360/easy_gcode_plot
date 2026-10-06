"""Compact HTML statistics, shared by the Qt viewer and portable export."""

import os
import tempfile
from functools import lru_cache
from html import escape
from pathlib import Path
from string import Template

from app.gcode.statistics_svg import statistics_svg
from app.gcode.trace_tools import trace_statistics

LABELS = {
    "heading": "Toolpath Statistics",
    "execution": "Execution",
    "complete": "complete",
    "partial": "PARTIAL / INVALID",
    "warnings": "WARNINGS",
    "movement_group": "Movements",
    "time_group": "Time",
    "bounds_group": "Bounds",
    "motions": "Motions",
    "executed_steps": "executed steps",
    "rapid_motions": "Rapid motions",
    "arc_motions": "arc motions",
    "cycle_motions": "cycle motions",
    "estimated_time": "Estimated motion time",
    "length": "Length",
    "rapid_length": "Rapid length",
    "feed_length": "Feed length",
    "rapid_time": "Rapid time",
    "feed_time": "Feed time",
    "known_time": "Known motion time",
    "average_feed": "Average feed",
    "unknown": "UNKNOWN",
    "unknown_time_motions": "Motions with unknown time",
    "rapid_speed": "Assumed rapid speed",
    "estimate_note": "Kinematic estimate only; excludes dwell, tool changes and acceleration.",
    "bounds": "Bounds in programmed coordinates",
    "tool": "Tool",
}


def write_statistics_html(path, html, *, source_path=None):
    """Atomically save a UTF-8 report, protecting the current NC source."""
    target = Path(path).resolve()
    if source_path:
        source = Path(source_path).resolve()
        if target == source or (target.exists() and source.exists() and target.samefile(source)):
            raise ValueError("The report cannot overwrite the source program")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(html)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export_execution_statistics(result, path, *, source_path, inches=False):
    """Single-file and batch HTML export over the same resolved execution."""
    write_statistics_html(
        path,
        statistics_html(
            trace_statistics(result),
            LABELS,
            inches=inches,
            title=Path(source_path).name,
            portable=True,
            execution=result,
        ),
        source_path=source_path,
    )


DEFAULT_THEME = {
    "background": "#ffffff",
    "foreground": "#252525",
    "panel": "#f3f5f7",
    "border": "#d6dce2",
    "muted": "#526271",
    "accent": "#21664f",
    "warning": "#a85400",
    "error": "#b42318",
    "size": 12.0,
    "page_margin": 20,
    "success_panel": "#e5f4ea",
    "warning_panel": "#fff0db",
    "error_panel": "#fce8e6",
}


@lru_cache(maxsize=8)
def _template(name):
    return Template((Path(__file__).with_name("templates") / name).read_text(encoding="utf-8"))


def _rows(rows):
    return "".join(
        _template("statistics_row.html").substitute(label=escape(str(label)), value=escape(str(value)))
        for label, value in rows
    )


def _table(rows, header=""):
    return '<table width="100%" cellspacing="0" cellpadding="0">' + header + _rows(rows) + "</table>"


def _group(label, kind="group"):
    return _template("statistics_group.html").substitute(label=escape(label), kind=kind)


def _duration(value, labels):
    if value is None:
        return labels["unknown"]
    hours, seconds = divmod(round(float(value) * 60), 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _section(values, labels, *, inches, index, name, header):
    scale, unit = (1 / 25.4, "in") if inches else (1, "mm")

    def length(value):
        return f"{float(value) * scale:.3f} {unit}"

    lengths = [
        (labels["length"], length(values["total_length"])),
        (labels["motions"], values["motion_count"]),
        (labels["rapid_length"], length(values["rapid_length"])),
        (labels["feed_length"], length(values["feed_length"])),
    ]
    average = values["average_feed_mm_min"]
    lengths.append((labels["average_feed"], length(average) + "/min" if average is not None else labels["unknown"]))
    if "rapid_feed_mm_min" in values:
        lengths.append((labels["rapid_speed"], length(values["rapid_feed_mm_min"]) + "/min"))
    times = [
        (labels[key], _duration(values[field], labels))
        for key, field in (
            ("rapid_time", "rapid_time_min"),
            ("feed_time", "feed_time_min"),
            ("known_time", "known_time_min"),
        )
    ]
    times.append((labels["unknown_time_motions"], values["unknown_time_motion_count"]))
    bounds = []
    if values.get("bounds") is not None:
        bounds = [
            (f"{axis} min / max", f"{length(low)} / {length(high)}")
            for axis, (low, high) in zip("XYZ", values["bounds"])
        ]
    estimated = values.get("total_time_min")
    if "total_time_min" not in values and values["unknown_time_motion_count"] == 0:
        estimated = values["known_time_min"]
    times.insert(0, (labels["estimated_time"], _duration(estimated, labels)))
    body = header
    if name != labels["heading"]:
        body += _rows([(labels["tool"], name)])
    metadata = _rows(
        (labels[key], values[field])
        for key, field in (
            ("executed_steps", "executed_step_count"),
            ("rapid_motions", "rapid_count"),
            ("arc_motions", "arc_count"),
            ("cycle_motions", "cycle_count"),
        )
        if field in values
    )
    body += _group(labels.get("movement_group", "Movements")) + metadata + _rows(lengths)
    body += _group(labels.get("time_group", "Time")) + _rows(times)
    if bounds:
        body += _group(f"{labels.get('bounds_group', 'Bounds')} ({unit})") + _rows(bounds)
    return _template("statistics_section.html").substitute(index=index, table=_table([], header=body))


def statistics_html(
    stats,
    labels,
    *,
    inches=False,
    selected=None,
    title="",
    portable=False,
    theme=None,
    execution=None,
    plot_segments=None,
):
    """Render the shared file template, with only aggregate values as input."""
    colors = {**DEFAULT_THEME, **({} if portable else theme or {})}
    if portable:
        colors["page_margin"] = 20
    size = float(colors["size"])
    colors["size"] = f"{size:.2f}pt"
    colors["page_margin"] = f"{colors['page_margin']}px"
    colors.update(heading_size=f"{size * 1.2:.2f}pt", note_size=f"{size * 0.85:.2f}pt")
    sections = [(None, labels["heading"], stats)] + [
        (tool, f"{labels['tool']} {tool}", values) for tool, values in stats["per_tool"].items()
    ]
    selector = ""
    if portable:
        options = "".join(
            f'<option value="section-{index}"{" selected" if key == selected else ""}>{escape(name)}</option>'
            for index, (key, name, _) in enumerate(sections)
        )
        selector = (
            '<div class="report-filter">'
            f'<label for="tool">{escape(labels["tool"])}</label>'
            f'<select id="tool">{options}</select></div>'
        )
    status_class = "status"
    status = labels["complete"]
    if not stats["execution_complete"]:
        status_class, status = "error", labels["partial"]
    elif stats.get("warning_count", 0):
        status_class = "warning"
        status = f"{labels.get('warnings', 'WARNINGS')} ({stats['warning_count']})"
    status_color = colors[{"status": "accent", "warning": "warning", "error": "error"}[status_class]]
    header = _group(labels["heading"], "report-title")
    if title and title != labels["heading"]:
        header += _group(title, "filename")
    header += '<tr><td class="metric-label">' + escape(labels["execution"]) + ":</td>"
    header += f'<td align="right" class="metric-value"><font color="{status_color}">{escape(status)}</font></td></tr>'
    rendered = "".join(
        _section(values, labels, inches=inches, index=index, name=name, header=header)
        for index, (key, name, values) in enumerate(sections)
        if portable or key == selected
    )
    script = ""
    if portable:
        script = "<script>" + _template("statistics_selector.js").template + "</script>"
    return _template("statistics.html").substitute(
        **colors,
        title=escape(title or labels["heading"]),
        status_class=status_class,
        status_background=colors[
            {"status": "success_panel", "warning": "warning_panel", "error": "error_panel"}[status_class]
        ],
        status_foreground=colors[{"status": "accent", "warning": "warning", "error": "error"}[status_class]],
        status=escape(f"{labels['execution']}: {status}"),
        selector=selector,
        sections=rendered,
        trajectory=statistics_svg(execution, stats, labels, inches=inches, segments=plot_segments)
        if portable and execution is not None
        else "",
        note=escape(labels["estimate_note"]),
        script=script,
    )
