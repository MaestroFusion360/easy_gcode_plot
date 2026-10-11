"""Validated physical tolerances for stock STL export."""

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


def limit_edges(triangles, length, cancelled):
    """Subdivide shared edges identically, including box walls and bottom faces."""
    pending = [np.asarray(triangles, dtype=np.float64)]
    while pending:
        if cancelled is not None and cancelled():
            raise InterruptedError("Stock STL export cancelled")
        batch = pending.pop()
        marked = np.linalg.norm(batch - np.roll(batch, -1, axis=1), axis=2) > length * (1 + 1e-10)
        small = ~np.any(marked, axis=1)
        if np.any(small):
            yield batch[small]
        selected = batch[~small]
        if len(selected):
            refined, _ = _split(selected, np.arange(len(selected)), marked[~small])
            pending.extend(refined[first : first + 65536] for first in range(0, len(refined), 65536))
