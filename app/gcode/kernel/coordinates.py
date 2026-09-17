"""Normalization helpers at the public coordinate-system boundary."""

from __future__ import annotations

WcsOffset = tuple[float, float] | tuple[float, float, float]
WcsOffsets = dict[int, WcsOffset]


def milling_wcs_offsets(
    wcs_offsets: WcsOffsets | None,
) -> dict[int, tuple[float, float, float]]:
    """Normalize public WCS values to XYZ for the milling kernel."""
    out = {}
    for code, values in (wcs_offsets or {}).items():
        if len(values) == 2:
            x, z = values
            out[code] = (float(x), 0.0, float(z))
        else:
            x, y, z = values
            out[code] = (float(x), float(y), float(z))
    return out


def turning_wcs_offsets(wcs_offsets: WcsOffsets | None) -> dict[int, tuple[float, float]]:
    """Normalize public WCS values to XZ for the turning kernel."""
    out = {}
    for code, values in (wcs_offsets or {}).items():
        if len(values) == 2:
            x, z = values
        else:
            x, _y, z = values
        out[code] = (float(x), float(z))
    return out


def published_wcs_offsets(
    offsets: dict[int, tuple[float, float] | tuple[float, float, float]],
) -> tuple[tuple[int, tuple[float, float, float]], ...]:
    """Return a deterministic XYZ representation for ``ExecutionResult``."""
    normalized = []
    for code, values in sorted(offsets.items()):
        xyz = (values[0], 0.0, values[1]) if len(values) == 2 else values
        normalized.append((int(code), tuple(float(value) for value in xyz)))
    return tuple(normalized)
