"""Convex clipping for persistent rapid-move damage on a turning stock section."""

from app.gcode.turning_tool_geometry import EPS
from app.native import native_symbol

_native_clip_regions = native_symbol("turning_collision", "clip_regions")


def _cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def polygon_area(points):
    """Signed section area (radius/Z coordinates)."""
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, (*points[1:], points[0]))) * 0.5


def clip_polygon(points, boundary):
    """Intersect a convex polygon with a convex material band; discard tangencies."""
    direction = 1 if polygon_area(boundary) > 0 else -1
    for a, b in zip(boundary, (*boundary[1:], boundary[0])):
        if not points:
            return ()
        result = []
        previous = points[-1]
        before = direction * _cross(a, b, previous)
        for point in points:
            after = direction * _cross(a, b, point)
            if (before >= 0) != (after >= 0):
                progress = before / (before - after)
                result.append(tuple(p + progress * (q - p) for p, q in zip(previous, point)))
            if after >= 0:
                result.append(point)
            previous, before = point, after
        points = tuple(result)
    return tuple(points) if len(points) >= 3 and abs(polygon_area(points)) > EPS else ()


def clip_regions(regions, bands):
    """Keep only damage that still belongs to the current material section."""
    if _native_clip_regions is not None:
        return _native_clip_regions(regions, bands)
    return _clip_regions_python(regions, bands)


def _clip_regions_python(regions, bands):
    """Reference implementation for source checkouts and native parity tests."""
    result = dict.fromkeys(clipped for region in regions for band in bands if (clipped := clip_polygon(region, band)))
    return tuple(result)


def update_regions(regions, sweeps, bands):
    """Clip existing marks after cutting, or add only new intersections for G0."""
    if not sweeps:
        return clip_regions(regions, bands)
    # G0 leaves material unchanged: previously clipped marks are already valid.
    added = clip_regions(sweeps, bands)
    return tuple(dict.fromkeys((*regions, *added))) if added else regions
