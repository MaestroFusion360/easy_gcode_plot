"""Text statistics and tool-list presentation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.gcode.core import format_gcode_number
from app.gcode.kernel import ExecutionResult
from app.tools.definitions import MILLING_TOOL_LABELS, TURNING_TOOL_LABELS

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

_TOOL_LIST_MILLING_LABELS = {
    **MILLING_TOOL_LABELS,
    "mill_flat": "Flat End Mill",
    "mill_bull": "Bull Nose End Mill",
    "mill_ball": "Ball End Mill",
}


def format_trace_statistics(
    stats: dict[str, object],
    *,
    inches: bool = False,
    labels: dict[str, str] | None = None,
) -> str:
    """Format trace-only metrics in millimetres or inches."""

    text = dict(LABELS)
    if labels:
        text.update(labels)

    length_scale = 1.0 / 25.4 if inches else 1.0
    length_unit = "in" if inches else "mm"

    def length(value):
        return float(value) * length_scale

    def duration(value):
        if value is None:
            return text["unknown"]
        seconds = round(value * 60)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def section(values):
        average = values["average_feed_mm_min"]
        return [
            f"{text['length']}: {length(values['total_length']):.3f} {length_unit}",
            f"{text['rapid_length']}: {length(values['rapid_length']):.3f} {length_unit}",
            f"{text['feed_length']}: {length(values['feed_length']):.3f} {length_unit}",
            f"{text['rapid_time']}: {duration(values['rapid_time_min'])}",
            f"{text['feed_time']}: {duration(values['feed_time_min'])}",
            f"{text['known_time']}: {duration(values['known_time_min'])}",
            f"{text['average_feed']}: "
            + (f"{length(average):.3f} {length_unit}/min" if average is not None else text["unknown"]),
            f"{text['unknown_time_motions']}: {values['unknown_time_motion_count']}",
        ]

    lines = [
        text["heading"],
        f"{text['execution']}: " + (text["complete"] if stats["execution_complete"] else text["partial"]),
        f"{text['motions']}: {stats['motion_count']}; {text['executed_steps']}: {stats['executed_step_count']}",
        f"{text['rapid_motions']}: {stats['rapid_count']}; "
        f"{text['arc_motions']}: {stats['arc_count']}; {text['cycle_motions']}: {stats['cycle_count']}",
        f"{text['estimated_time']}: {duration(stats['total_time_min'])}",
        *section(stats),
        f"{text['rapid_speed']}: {length(stats['rapid_feed_mm_min']):.3f} {length_unit}/min",
        text["estimate_note"],
    ]

    def bounds_section(values):
        bounds = values.get("bounds")
        if bounds is None:
            return []
        return [
            f"{text['bounds']} ({length_unit}):",
            *[f"{axis}: {length(low):.3f} / {length(high):.3f}" for axis, (low, high) in zip("XYZ", bounds)],
        ]

    lines.extend(bounds_section(stats))
    for tool, values in stats["per_tool"].items():
        lines.extend(["", f"{text['tool']} {tool}", *section(values)])
        lines.extend(bounds_section(values))
    return "\n".join(lines)


def _tool_sort_key(item: tuple[str, object]) -> tuple[int, int | str]:
    key = item[0].upper()
    digits = key[1:] if key.startswith("T") else key
    return (0, int(digits)) if digits.isdigit() else (1, key)


def _tool_spec(tools: dict[str, dict], key: str) -> dict:
    direct = tools.get(key)
    if direct is not None:
        return direct
    target = key[1:] if key.upper().startswith("T") else key
    if target.isdigit():
        number = int(target)
        for candidate, spec in tools.items():
            candidate_number = str(candidate).upper().removeprefix("T")
            if candidate_number.isdigit() and int(candidate_number) == number:
                return spec
    return {}


def _tool_description(spec: dict, *, turning: bool) -> str:
    tool_type = str(spec.get("type", "")).strip().lower()
    labels = TURNING_TOOL_LABELS if turning else _TOOL_LIST_MILLING_LABELS
    description = str(spec.get("description", "")).strip() or labels.get(tool_type, tool_type.replace("_", " "))
    return description.upper() or "UNCONFIGURED TOOL"


def _tool_information(spec: dict, z_min: float | None, *, turning: bool) -> str:
    geometry = []
    if "diameter" in spec:
        geometry.append(f"D={format_gcode_number(spec['diameter'])}")
    radius_key = "noseRadius" if turning else "cornerRadius"
    if radius_key in spec:
        geometry.append(f"CR={format_gcode_number(spec[radius_key])}")
    if "tipAngle" in spec:
        geometry.append(f"TAPER={format_gcode_number(spec['tipAngle'])}DEG")
    if turning and "tipOrientation" in spec:
        geometry.append(f"P={int(spec['tipOrientation'])}")
    sections = [" ".join(geometry)] if geometry else []
    if z_min is not None:
        sections.append(f"ZMIN={format_gcode_number(z_min)}")
    sections.append(_tool_description(spec, turning=turning))
    return " - ".join(sections)


def _program_number(result: ExecutionResult, path: Path | None) -> str:
    for event in result.events:
        if event.kind == "program_start" and event.program_number is not None:
            return str(event.program_number)
    return path.stem if path is not None else "Untitled"


def format_tool_list(
    result: ExecutionResult,
    statistics: dict[str, object],
    tools: dict[str, dict],
    *,
    file_path: str | None = None,
    turning: bool = False,
) -> str:
    """Format a compact CIMCO-style list of tools used by the resolved trace."""
    path = Path(file_path).resolve() if file_path else None
    program = _program_number(result, path)
    try:
        created = datetime.fromtimestamp(path.stat().st_ctime).strftime("%d.%m.%Y %H:%M:%S") if path else "-"
    except OSError:
        created = "-"
    file_name = path.name if path else "Untitled"
    full_name = str(path) if path else "-"
    lines = [
        f"Tool List: {program}",
        "",
        f"{'File':18}: {file_name}",
        f"{'Program':18}: {program}",
        f"{'Full name':18}: {full_name}",
        f"{'Created':18}: {created}",
        "",
        f"{'Tool number':16}Tool information",
        "",
    ]
    per_tool = statistics.get("per_tool", {})
    for key, values in sorted(per_tool.items(), key=_tool_sort_key):
        if key == "unknown":
            continue
        spec = _tool_spec(tools, key)
        lines.append(f"{key:<16}{_tool_information(spec, values.get('z_min'), turning=turning)}")
    return "\n".join(lines)
