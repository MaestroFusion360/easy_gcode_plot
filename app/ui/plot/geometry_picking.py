"""Geometry-based point picking shared by fixed plot views."""

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PickPoint:
    point: tuple[float, float, float]
    pixels: float
    depth: float = 0.0


def view_projection(view):
    viewport = view.getViewport()
    try:
        projection = view.projectionMatrix(viewport, viewport)
    except TypeError:  # pyqtgraph < 0.14
        projection = view.projectionMatrix(viewport)
    return projection * view.viewMatrix(), viewport


def project_points(points, matrix, viewport):
    """Project physical XYZ to logical widget pixels, retaining clip depth."""
    points = np.asarray(points, dtype=float).reshape(-1, 3)
    homogeneous = np.column_stack((points, np.ones(len(points))))
    clip = homogeneous @ np.asarray(matrix.copyDataTo()).reshape(4, 4).T
    valid = clip[:, 3] > 1e-12
    ndc = np.full((len(points), 3), np.nan)
    ndc[valid] = clip[valid, :3] / clip[valid, 3, None]
    x, y, width, height = viewport
    return np.column_stack((x + (ndc[:, 0] + 1) * width / 2, y + (1 - ndc[:, 1]) * height / 2, ndc[:, 2]))


def pick_segments(position, segments, matrix, viewport, tolerance=8.0):
    """Snap to an endpoint or the closest point on a displayed geometry edge."""
    segments = np.asarray(segments, dtype=float).reshape(-1, 2, 3)
    if len(segments) == 0:
        return None
    projected = project_points(segments.reshape(-1, 3), matrix, viewport).reshape(-1, 2, 3)
    delta = projected[:, 1, :2] - projected[:, 0, :2]
    offset = np.asarray(position) - projected[:, 0, :2]
    length2 = np.sum(delta * delta, axis=1)
    progress = np.clip(np.sum(offset * delta, axis=1) / np.maximum(length2, 1e-30), 0, 1)
    nearest = projected[:, 0, :2] + progress[:, None] * delta
    distances = np.linalg.norm(nearest - position, axis=1)
    valid = np.isfinite(distances) & (distances <= tolerance)
    if not np.any(valid):
        return None
    indices = np.flatnonzero(valid)
    index = indices[np.argmin(distances[valid])]
    t = progress[index]
    endpoint_distances = np.linalg.norm(projected[index, :, :2] - position, axis=1)
    endpoint = np.argmin(endpoint_distances)
    if endpoint_distances[endpoint] <= tolerance:
        t = float(endpoint)
    # Perspective screen interpolation is not linear in world coordinates.
    transform = np.asarray(matrix.copyDataTo()).reshape(4, 4)
    weights = np.column_stack((segments[index], np.ones(2))) @ transform[3]
    t = (t / weights[1]) / ((1 - t) / weights[0] + t / weights[1])
    point = segments[index, 0] + t * (segments[index, 1] - segments[index, 0])
    return PickPoint(tuple(point), float(distances[index]), float(projected[index, 0, 2]))


def cursor_ray(position, matrix, viewport):
    x, y, width, height = viewport
    ndc = ((position[0] - x) * 2 / width - 1, 1 - (position[1] - y) * 2 / height)
    inverse = np.linalg.inv(np.asarray(matrix.copyDataTo()).reshape(4, 4))
    endpoints = np.asarray([(*ndc, -1, 1), (*ndc, 1, 1)]) @ inverse.T
    endpoints = endpoints[:, :3] / endpoints[:, 3, None]
    direction = endpoints[1] - endpoints[0]
    return endpoints[0], direction / np.linalg.norm(direction)


def pick_triangles(position, triangles, matrix, viewport):
    """Hit the nearest visible facet, including translucent and clipped meshes."""
    origin, direction = cursor_ray(position, matrix, viewport)
    best = None
    for begin in range(0, len(triangles), 65536):
        chunk = np.asarray(triangles[begin : begin + 65536], dtype=float)
        first, second = chunk[:, 1] - chunk[:, 0], chunk[:, 2] - chunk[:, 0]
        cross = np.cross(direction, second)
        determinant = np.einsum("ij,ij->i", first, cross)
        usable = np.abs(determinant) > 1e-12
        inverse = np.divide(1.0, determinant, out=np.zeros_like(determinant), where=usable)
        offset = origin - chunk[:, 0]
        u = np.einsum("ij,ij->i", offset, cross) * inverse
        q = np.cross(offset, first)
        v = q @ direction * inverse
        depth = np.einsum("ij,ij->i", second, q) * inverse
        valid = usable & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (depth >= 0)
        if np.any(valid):
            distance = float(np.min(depth[valid]))
            if best is None or distance < best.depth:
                best = PickPoint(tuple(origin + distance * direction), 0.0, distance)
    return best


def plane_point(position, matrix, viewport, plane, reference):
    """Continue a live ruler over empty space at its first point's depth."""
    origin, direction = cursor_ray(position, matrix, viewport)
    normal_axis = {"xy": 2, "xz": 1, "yz": 0}[plane]
    if abs(direction[normal_axis]) < 1e-12:
        return None
    distance = (reference[normal_axis] - origin[normal_axis]) / direction[normal_axis]
    return tuple(origin + distance * direction)


def pick_grid(position, grid, matrix, viewport, tolerance=8.0):
    """Snap to an actual rendered grid crossing, including its offset and rotation."""
    origin, direction = cursor_ray(position, matrix, viewport)
    transform = np.asarray(grid.transform().copyDataTo()).reshape(4, 4)
    inverse = np.linalg.inv(transform)
    local_origin = (inverse @ np.append(origin, 1.0))[:3]
    local_direction = inverse[:3, :3] @ direction
    if abs(local_direction[2]) < 1e-12:
        return None
    point = local_origin - local_direction * (local_origin[2] / local_direction[2])
    size = np.asarray(grid.size()[:2], dtype=float)
    spacing = np.asarray(grid.spacing()[:2], dtype=float)
    if np.any(spacing <= 0):
        return None
    first = -size / 2.0
    indices = np.rint((point[:2] - first) / spacing)
    last = np.floor((size + spacing * 0.001) / spacing)
    if np.any(indices < 0) or np.any(indices > last):
        return None
    crossing = first + indices * spacing
    world = (transform @ np.array((*crossing, 0.0, 1.0)))[:3]
    screen = project_points([world], matrix, viewport)[0]
    pixels = float(np.linalg.norm(screen[:2] - position))
    if not math.isfinite(pixels) or pixels > tolerance:
        return None
    return PickPoint(tuple(world), pixels, float(screen[2]))
