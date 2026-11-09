"""Shared parallel camera geometry for the plot and its orientation cube."""

from __future__ import annotations

import math

from PyQt6.QtGui import QVector3D


def camera_basis(yaw, pitch):
    """Return eye, screen-right and screen-up unit vectors, including pole views."""
    azimuth, elevation = math.radians(yaw), math.radians(pitch)
    return (
        QVector3D(
            math.cos(elevation) * math.cos(azimuth),
            math.cos(elevation) * math.sin(azimuth),
            math.sin(elevation),
        ),
        QVector3D(-math.sin(azimuth), math.cos(azimuth), 0),
        QVector3D(
            -math.sin(elevation) * math.cos(azimuth),
            -math.sin(elevation) * math.sin(azimuth),
            math.cos(elevation),
        ),
    )
