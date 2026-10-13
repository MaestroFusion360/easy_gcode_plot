"""Immutable milling calculator parameters and preview geometry."""

from __future__ import annotations

from dataclasses import dataclass

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class PocketParameters:
    tool_diameter: float = 10.0
    pocket_diameter: float = 100.0
    pocket_width: float = 100.0
    pocket_height: float = 100.0
    corner_radius: float = 0.0
    stepover: float = 5.0
    center_x: float = 0.0
    center_y: float = 0.0
    z_reference: float = 10.0
    z_start: float = 0.0
    z_end: float = -2.0
    z_step: float = 1.0
    stock_xy: float = 0.0
    stock_z: float = 0.0
    feed: float = 1000.0
    circular: bool = True
    ccw: bool = True
    spiral: bool = False
    correction: bool = False
    helix: bool = False


@dataclass(frozen=True, slots=True)
class PocketPreviewGeometry:
    boundary: tuple[Point, ...]
    paths: tuple[tuple[Point, ...], ...]
