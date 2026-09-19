"""Composable coordinate transforms used by the milling interpreter."""

from __future__ import annotations

import math
from dataclasses import dataclass

Point3 = tuple[float, float, float]


@dataclass(frozen=True)
class CoordinateTransform:
    """Program-coordinate transform applied before the active WCS offset."""

    translation: Point3 = (0.0, 0.0, 0.0)
    rotation_center: Point3 = (0.0, 0.0, 0.0)
    rotation_degrees: float = 0.0
    rotation_plane: int = 17
    scale_center: Point3 = (0.0, 0.0, 0.0)
    scale_factors: Point3 = (1.0, 1.0, 1.0)

    def _rotate(self, point: Point3, degrees: float) -> Point3:
        if abs(degrees) <= 1e-12:
            return point
        axes = {17: (0, 1), 18: (0, 2), 19: (1, 2)}
        first, second = axes.get(self.rotation_plane, (0, 1))
        center = self.rotation_center
        values = list(point)
        a = point[first] - center[first]
        b = point[second] - center[second]
        radians = math.radians(degrees)
        cosine = math.cos(radians)
        sine = math.sin(radians)
        values[first] = center[first] + a * cosine - b * sine
        values[second] = center[second] + a * sine + b * cosine
        return values[0], values[1], values[2]

    def apply(self, point: Point3) -> Point3:
        tx, ty, tz = self.translation
        translated = point[0] + tx, point[1] + ty, point[2] + tz
        rotated = self._rotate(translated, self.rotation_degrees)
        if all(abs(factor - 1.0) <= 1e-12 for factor in self.scale_factors):
            return rotated
        center = self.scale_center
        scaled = list(rotated)
        for axis, factor in enumerate(self.scale_factors):
            scaled[axis] = center[axis] + (rotated[axis] - center[axis]) * factor
        return scaled[0], scaled[1], scaled[2]

    def inverse(self, point: Point3) -> Point3:
        unscaled = point
        if any(abs(factor - 1.0) > 1e-12 for factor in self.scale_factors):
            center = self.scale_center
            values = list(point)
            for axis, factor in enumerate(self.scale_factors):
                values[axis] = center[axis] + (point[axis] - center[axis]) / factor
            unscaled = values[0], values[1], values[2]
        unrotated = self._rotate(unscaled, -self.rotation_degrees)
        tx, ty, tz = self.translation
        return unrotated[0] - tx, unrotated[1] - ty, unrotated[2] - tz

    def apply_vector(self, vector: Point3) -> Point3:
        """Apply the transform's linear part to an I/J/K displacement."""
        first, second = {17: (0, 1), 18: (0, 2), 19: (1, 2)}.get(self.rotation_plane, (0, 1))
        radians = math.radians(self.rotation_degrees)
        cosine = math.cos(radians)
        sine = math.sin(radians)
        values = list(vector)
        values[first] = vector[first] * cosine - vector[second] * sine
        values[second] = vector[first] * sine + vector[second] * cosine
        rotated = values[0], values[1], values[2]
        scaled = list(rotated)
        for axis, factor in enumerate(self.scale_factors):
            scaled[axis] *= factor
        return scaled[0], scaled[1], scaled[2]

    def plane_scale_factors(self, plane: int) -> tuple[float, float]:
        """Return scale factors for the two axes of an interpolation plane."""
        first, second = {17: (0, 1), 18: (0, 2), 19: (1, 2)}.get(plane, (0, 1))
        return self.scale_factors[first], self.scale_factors[second]
