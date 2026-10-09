"""Static report projections using the same page layout and styling as Print."""

from html import escape

from app.gcode.plot_page import fit_plot_bounds, print_line_style
from app.gcode.trace_tools import sample_motion


def _trace_segments(result):
    turning = result.language == "fanuc_turn"
    for index, motion in enumerate(result.motions):
        previous = (motion.start_x * (0.5 if turning else 1), motion.start_y, motion.start_z)
        for point in sample_motion(motion, index, chord_error=0.002, lathe_radius_view=turning):
            current = (point.x, point.y, point.z)
            yield previous, current, motion.move, motion.tool
            previous = current


def _projected_paths(result, segments):
    horizontal, vertical = (2, 0) if result.language == "fanuc_turn" else (0, 1)
    paths = {}
    left = top = float("inf")
    right = bottom = float("-inf")
    for start, end, move, tool in segments:
        a, b = (start[horizontal], -start[vertical]), (end[horizontal], -end[vertical])
        left, right = min(left, a[0], b[0]), max(right, a[0], b[0])
        top, bottom = min(top, a[1], b[1]), max(bottom, a[1], b[1])
        color, width = print_line_style(move)
        paths.setdefault((tool, color, width, move == 0), []).append((a, b))
    return paths, (left, right, top, bottom)


def statistics_svg(result, stats, labels, *, inches=False, segments=None):
    """Use the complete Print trace, with fixed XY or XZ projection."""
    if not result.motions:
        return ""
    turning = result.language == "fanuc_turn"
    projection = "XZ" if turning else "XY"
    paths, bounds = _projected_paths(result, _trace_segments(result) if segments is None else segments)
    if not paths:
        return ""
    width, height = 900, 636
    # Keep the coordinate origin visible even when all toolpaths are offset.
    left, right, top, bottom = bounds
    bounds = min(left, 0), max(right, 0), min(top, 0), max(bottom, 0)
    # A landscape page, with Print's 12 mm margins and physical pen widths.
    unit = width / 297
    margin = 12 * unit
    scale, offset_x, offset_y = fit_plot_bounds(bounds, (margin, margin, width - 2 * margin, height - 2 * margin))
    tools = {tool: index + 1 for index, tool in enumerate(stats["per_tool"])}
    drawing = []
    for (tool, color, pen_width, rapid), lines in paths.items():
        commands = " ".join(
            f"M{offset_x + a[0] * scale:.3f},{offset_y + a[1] * scale:.3f} "
            f"L{offset_x + b[0] * scale:.3f},{offset_y + b[1] * scale:.3f}"
            for a, b in lines
        )
        dash = f' stroke-dasharray="{4 * pen_width * unit:.3f} {2 * pen_width * unit:.3f}"' if rapid else ""
        drawing.append(
            f'<path data-tool-section="section-{tools.get(tool or "unknown", 0)}" '
            f'class="svg-{"rapid" if rapid else "cut"}" stroke="{color}" '
            f'stroke-width="{pen_width * unit:.3f}"{dash} d="{commands}"/>'
        )
    displayed_unit = "in" if inches else "mm"
    axes = "Z horizontal / X vertical" if turning else "X horizontal / Y vertical"
    horizontal, vertical = ("Z", "X") if turning else ("X", "Y")
    x, y = offset_x, offset_y
    origin = (
        '<g class="coordinate-origin" stroke="#526477" stroke-width="1.2" fill="#526477">'
        "<title>0: calculated trajectory coordinate origin</title>"
        f'<line x1="{x:.3f}" y1="{y:.3f}" x2="{x + 24:.3f}" y2="{y:.3f}"/>'
        f'<polygon points="{x + 24:.3f},{y:.3f} {x + 19:.3f},{y - 3:.3f} {x + 19:.3f},{y + 3:.3f}"/>'
        f'<line x1="{x:.3f}" y1="{y:.3f}" x2="{x:.3f}" y2="{y - 24:.3f}"/>'
        f'<polygon points="{x:.3f},{y - 24:.3f} {x - 3:.3f},{y - 19:.3f} {x + 3:.3f},{y - 19:.3f}"/>'
        f'<circle cx="{x:.3f}" cy="{y:.3f}" r="3" fill="white"/>'
        '<g stroke="none" font-family="sans-serif" font-size="12">'
        f'<text x="{x + 24:.3f}" y="{y + 16:.3f}" text-anchor="middle">+{horizontal}</text>'
        f'<text x="{x:.3f}" y="{y - 28:.3f}" text-anchor="middle">+{vertical}</text>'
        f'<text x="{x - 7:.3f}" y="{y + 15:.3f}" text-anchor="end">0</text>'
        "</g></g>"
    )
    return (
        '<div class="trajectory-preview">'
        f"<h2>{escape(labels.get('trajectory', 'Toolpath'))} - {projection}</h2>"
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{projection} {escape(labels.get("trajectory", "Toolpath"))}">'
        f"<title>{projection} - {axes} ({displayed_unit})</title>"
        '<rect width="100%" height="100%" fill="white"/>'
        f'<g fill="none" stroke-linecap="round">{"".join(drawing)}</g>{origin}</svg></div>'
    )
