"""Machine-neutral two-stage reference-return mechanics."""

from __future__ import annotations

from dataclasses import dataclass

Point = tuple[float, ...]
Segment = tuple[Point, Point]


@dataclass(frozen=True)
class ReferenceReturn:
    """Two-stage G28/G30 path in machine coordinates."""

    segments: tuple[Segment, ...]
    target: Point


def reference_return(
    start: Point,
    intermediate: Point,
    home: Point,
    addressed: tuple[bool, ...],
    *,
    tolerance: float = 0.0,
) -> ReferenceReturn:
    if not len(start) == len(intermediate) == len(home) == len(addressed):
        raise ValueError("Reference-return coordinates must have the same dimensionality")

    def different(first: Point, second: Point) -> bool:
        return any(abs(a - b) > tolerance for a, b in zip(first, second, strict=True))

    target = tuple(home[index] if addressed[index] else intermediate[index] for index in range(len(start)))
    segments: list[Segment] = []
    if different(start, intermediate):
        segments.append((start, intermediate))
    if different(intermediate, target):
        segments.append((intermediate, target))
    return ReferenceReturn(tuple(segments), target)
