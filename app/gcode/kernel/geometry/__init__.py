"""Geometric construction: profiles, arcs, clipping and coordinate systems."""

from .arcs import resolve_arc
from .coordinates import WcsOffset, WcsOffsets, milling_wcs_offsets, published_wcs_offsets, turning_wcs_offsets
from .direct import apply_a_programming, apply_corner_direct_programming, build_profile_segments
from .profile_arcs import (
    arc_center_from_r,
    arc_progress01,
    is_point_on_arc,
    normalize_sweep,
    score_center_candidate,
    segment_points,
    try_compute_signed_arc_radius_from_center,
    try_get_arc_geometry,
)
from .profile_clip import clip_polyline_max_x, clip_polyline_min_x, intersect_at_x, try_find_entry_on_profile
from .transform import CoordinateTransform

__all__ = [
    "WcsOffset",
    "WcsOffsets",
    "CoordinateTransform",
    "apply_a_programming",
    "apply_corner_direct_programming",
    "arc_center_from_r",
    "arc_progress01",
    "build_profile_segments",
    "clip_polyline_max_x",
    "clip_polyline_min_x",
    "intersect_at_x",
    "is_point_on_arc",
    "milling_wcs_offsets",
    "normalize_sweep",
    "published_wcs_offsets",
    "resolve_arc",
    "score_center_candidate",
    "segment_points",
    "try_compute_signed_arc_radius_from_center",
    "try_find_entry_on_profile",
    "try_get_arc_geometry",
    "turning_wcs_offsets",
]
