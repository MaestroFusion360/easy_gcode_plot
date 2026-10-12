"""Validated physical tolerances for stock STL export."""

# pylint: disable=use-implicit-booleaness-not-len  # ndarray truthiness is ambiguous.

import math
from dataclasses import dataclass

import numpy as np


def _split(xy, owners, marked, midpoint=None):
    triangles, ids = [], []
    masks = marked @ np.asarray((1, 2, 4))
    if midpoint is None:
        midpoint = (xy + np.roll(xy, -1, axis=1)) / 2
    patterns = {
        0: ((0, 1, 2),),
        1: ((0, 3, 2), (3, 1, 2)),
        2: ((1, 4, 0), (4, 2, 0)),
        4: ((2, 5, 1), (5, 0, 1)),
        3: ((1, 4, 3), (2, 0, 3), (2, 3, 4)),
        6: ((2, 5, 4), (0, 1, 4), (0, 4, 5)),
        5: ((0, 3, 5), (1, 2, 5), (1, 5, 3)),
        7: ((0, 3, 5), (3, 1, 4), (5, 4, 2), (3, 4, 5)),
    }
    for mask, pattern in patterns.items():
        selected = masks == mask
        if not np.any(selected):
            continue
        vertices = np.concatenate((xy[selected], midpoint[selected]), axis=1)
        triangles.append(vertices[:, pattern].reshape(-1, 3, xy.shape[2]))
        ids.append(np.repeat(owners[selected], len(pattern)))
    return np.concatenate(triangles), np.concatenate(ids)


@dataclass(frozen=True)
class StockStlOptions:
    units: str = "mm"
    linear_deviation: float = 0.1
    angular_deviation: float = 15.0
    edge_length: float = 5.0
    calculated: bool = False

    def validate(self):
        if self.units not in {"mm", "in"}:
            raise ValueError("STL units must be mm or in")
        for value, low, high, name in (
            (self.linear_deviation, 0.001, 1.0, "Linear deviation"),
            (self.angular_deviation, 1.0, 90.0, "Angular deviation"),
            (self.edge_length, 0.05, 100.0, "Edge length"),
        ):
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name}: expected {low}..{high}")
        return self

    @property
    def scale(self):
        return 1 / 25.4 if self.units == "in" else 1.0

    def sampling_step(self, sweeps):
        radii = [float(s.tool["diameter"]) / 2 for s in sweeps]
        radii.extend(float(s.tool.get("cornerRadius", 0)) for s in sweeps if s.tool.get("cornerRadius", 0) > 0)
        radius = min(radii, default=1.0)
        sagitta = min(self.linear_deviation, radius)
        linear = 2 * math.sqrt(sagitta * (2 * radius - sagitta))
        angular = 2 * radius * math.sin(math.radians(self.angular_deviation) / 2)
        return min(self.edge_length, linear, angular) / math.sqrt(3)

    def contour_error(self, sweep):
        radius = float(sweep.tool["diameter"]) / 2
        return min(self.linear_deviation, radius * (1 - math.cos(math.radians(self.angular_deviation) / 2)))


def _bilinear_height(stock, xy):
    """Sample the same piecewise-bilinear surface rendered by the GPU."""
    u = np.clip((xy[..., 0] - stock.spec.x_min) / stock.dx, 0, stock.nx)
    v = np.clip((xy[..., 1] - stock.spec.y_min) / stock.dy, 0, stock.ny)
    x = np.minimum(np.floor(u).astype(np.intp), stock.nx - 1)
    y = np.minimum(np.floor(v).astype(np.intp), stock.ny - 1)
    fx = u - x
    fy = v - y
    height = stock.height
    return (
        (1 - fx) * (1 - fy) * height[y, x]
        + fx * (1 - fy) * height[y, x + 1]
        + fx * fy * height[y + 1, x + 1]
        + (1 - fx) * fy * height[y + 1, x]
    )


def _surface_edges(triangles, stock, options):
    """Return exact surface midpoints and edge refinement requirements.

    Linear error is the sag of a bilinear edge relative to its STL chord.
    Angular error is the maximum tangent/chord angle on that edge. Both
    depend only on the shared edge, so adjacent facets split consistently.
    """
    next_vertices = np.roll(triangles, -1, axis=1)
    midpoint = (triangles + next_vertices) * 0.5
    z = _bilinear_height(stock, midpoint[..., :2])
    sag = z - midpoint[..., 2]
    midpoint[..., 2] = z
    delta = next_vertices - triangles
    # Along a straight XY edge inside a bilinear patch, height is quadratic.
    # The coefficient of t^2 is determined exactly by the midpoint sample.
    curvature = -4 * sag
    horizontal2 = np.sum(delta[..., :2] ** 2, axis=-1)
    horizontal = np.sqrt(horizontal2)
    dz = delta[..., 2]
    cross = horizontal * np.abs(curvature)
    angle0 = np.arctan2(cross, horizontal2 + dz * (dz - curvature))
    angle1 = np.arctan2(cross, horizontal2 + dz * (dz + curvature))
    bend = np.maximum(angle0, angle1)
    marked = (np.abs(sag) > options.linear_deviation) | (bend > np.deg2rad(options.angular_deviation))
    return midpoint, marked


def limit_edges(triangles, length, cancelled, *, stock=None, options=None):
    """Conforming edge bisection; optionally follow the actual GPU bilinear surface.

    Curvature correction applies only to the top surface. Walls and bottom
    are planar, and their shared edges must retain identical split points.
    These tolerances measure tessellation of the sampled heightfield, not
    machining error smaller than the GPU grid pitch.
    """
    pending = [np.asarray(triangles, dtype=np.float64)]
    while pending:
        if cancelled is not None and cancelled():
            raise InterruptedError("Stock STL export cancelled")
        batch = pending.pop()
        if not len(batch):
            continue
        next_vertices = np.roll(batch, -1, axis=1)
        marked = np.linalg.norm(batch - next_vertices, axis=2) > length * (1 + 1e-10)
        midpoint = None
        if stock is not None and options is not None:
            midpoint, curved = _surface_edges(batch, stock, options)
            marked |= curved
        small = ~np.any(marked, axis=1)
        if np.any(small):
            yield batch[small]
        selected = batch[~small]
        if len(selected):
            selected_midpoints = None if midpoint is None else midpoint[~small]
            refined, _ = _split(selected, np.arange(len(selected)), marked[~small], selected_midpoints)
            pending.extend(refined[first : first + 65536] for first in range(0, len(refined), 65536))
