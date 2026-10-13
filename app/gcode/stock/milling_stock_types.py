"""Physical milling stock bounds and detached GPU snapshot contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MillingStockSpec:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
    resolution: float = 1.0

    def validate(self):
        values = (self.x_min, self.x_max, self.y_min, self.y_max, self.z_min, self.z_max, self.resolution)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("Stock bounds and resolution must be finite")
        if not (self.x_min < self.x_max and self.y_min < self.y_max and self.z_min < self.z_max):
            raise ValueError("Stock must have positive X, Y and Z dimensions")
        if self.resolution <= 0:
            raise ValueError("Stock resolution must be positive")

    @property
    def bounds(self):
        return ((self.x_min, self.x_max), (self.y_min, self.y_max), (self.z_min, self.z_max))


@dataclass(frozen=True)
class MillingStockSnapshot:
    spec: MillingStockSpec
    height: np.ndarray
    rapid: np.ndarray
    dx: float
    dy: float
    sweeps: tuple = ()
    motions: tuple = ()

    @property
    def nx(self):
        return self.height.shape[1] - 1

    @property
    def ny(self):
        return self.height.shape[0] - 1
