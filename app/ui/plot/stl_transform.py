"""Pure-numpy STL scene-object transforms: pivot, rotate, mirror, arrays, sections.

The source mesh is never modified. Each object keeps a 4x4 matrix, so any edit
is recomputed from the original and rotations do not accumulate error.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import mapbox_earcut
import numpy as np

from .stl import StlMesh

_EPS = 1e-9
_FLOAT32_MAX = 3.4028234663852886e38
_AXES = {"X": 0, "Y": 1, "Z": 2}


def translation(offset) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = np.asarray(offset, dtype=float)
    return matrix


def rotation(axis: str, angle_deg: float, about=(0.0, 0.0, 0.0)) -> np.ndarray:
    """Right-handed rotation around a world axis passing through `about`."""
    index = _AXES[axis.upper()]
    angle = np.radians(angle_deg)
    cos, sin = np.cos(angle), np.sin(angle)
    i, j = (index + 1) % 3, (index + 2) % 3
    rot = np.eye(4)
    rot[i, i], rot[i, j], rot[j, i], rot[j, j] = cos, -sin, sin, cos
    about = np.asarray(about, dtype=float)
    return translation(about) @ rot @ translation(-about)


def mirror(plane: str, about=(0.0, 0.0, 0.0)) -> np.ndarray:
    """Mirror across the plane normal to axis: 'X' -> YZ plane, etc."""
    scale = np.eye(4)
    scale[_AXES[plane.upper()], _AXES[plane.upper()]] = -1.0
    about = np.asarray(about, dtype=float)
    return translation(about) @ scale @ translation(-about)


@dataclass(frozen=True)
class StlObject:
    mesh: StlMesh
    name: str = "STL"
    matrix: np.ndarray = field(default_factory=lambda: np.eye(4))
    pivot: tuple[float, float, float] = (0.0, 0.0, 0.0)  # in source-mesh coordinates
    pivot_mode: str = "point"

    def world_pivot(self) -> np.ndarray:
        return (self.matrix @ np.append(self.pivot, 1.0))[:3]

    def with_matrix(self, matrix: np.ndarray) -> StlObject:
        return replace(self, matrix=matrix)

    def set_pivot(self, mode: str = "center", point=None) -> StlObject:
        """Choose base point: 'center', 'min' (bbox corner), 'origin' or explicit source-space point."""
        (x0, x1), (y0, y1), (z0, z1) = self.mesh.bounds
        if mode == "center":
            new = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        elif mode == "min":
            new = (x0, y0, z0)
        elif mode == "origin":
            new = (0.0, 0.0, 0.0)
        elif mode in {"point", "custom"} and point is not None:
            new = tuple(float(v) for v in point)
        else:
            raise ValueError(f"Unknown pivot mode: {mode}")
        return replace(self, pivot=new, pivot_mode="custom" if mode == "point" else mode)

    def move_pivot_to(self, target) -> StlObject:
        """Place the base point at world coordinates `target`."""
        delta = np.asarray(target, dtype=float) - self.world_pivot()
        return self.with_matrix(translation(delta) @ self.matrix)

    def rotate(self, axis: str, angle_deg: float) -> StlObject:
        """Rotate around a world axis through the current base point."""
        return self.with_matrix(rotation(axis, angle_deg, self.world_pivot()) @ self.matrix)

    def mirrored(self, plane: str) -> StlObject:
        """Mirror across the world plane through the base point."""
        return self.with_matrix(mirror(plane, self.world_pivot()) @ self.matrix)

    def scaled(self, factor: float) -> StlObject:
        factor = float(factor)
        if not np.isfinite(factor) or factor <= 0.0:
            raise ValueError("Scale factor must be finite and greater than zero")
        scale = np.diag((factor, factor, factor, 1.0))
        pivot = self.world_pivot()
        matrix = translation(pivot) @ scale @ translation(-pivot) @ self.matrix
        source = self.mesh.triangles.astype(np.float64)
        transformed64 = source @ matrix[:3, :3].T + matrix[:3, 3]
        if not np.isfinite(transformed64).all() or np.max(np.abs(transformed64)) > _FLOAT32_MAX:
            raise ValueError("Scale would exceed the STL mesh's coordinate range")
        if np.linalg.det(matrix[:3, :3]) < 0:
            transformed64 = transformed64[:, (0, 2, 1), :]
        transformed = transformed64.astype(np.float32)
        source_area = np.linalg.norm(np.cross(source[:, 1] - source[:, 0], source[:, 2] - source[:, 0]), axis=1)
        transformed64 = transformed.astype(np.float64)
        transformed_area = np.linalg.norm(
            np.cross(transformed64[:, 1] - transformed64[:, 0], transformed64[:, 2] - transformed64[:, 0]), axis=1
        )
        if not np.isfinite(transformed).all() or np.any((source_area > 0.0) & (transformed_area == 0.0)):
            raise ValueError("Scale would exceed the STL mesh's coordinate precision")
        if measure_mesh(source).volume is not None and measure_mesh(transformed).volume is None:
            raise ValueError("Scale would make the closed STL mesh numerically invalid")
        return self.with_matrix(matrix)

    def world_triangles(self) -> np.ndarray:
        """(N,3,3) triangles in world space; winding fixed if the matrix mirrors."""
        return transform_triangles(self.mesh.triangles, self.matrix)


@dataclass(frozen=True)
class MeshMeasurements:
    area: float
    volume: float | None
    center_of_mass: tuple[float, float, float] | None
    bounds: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


def measure_mesh(triangles: np.ndarray) -> MeshMeasurements:
    """Measure a mesh in world coordinates; solid properties require a closed shell."""
    triangles = np.asarray(triangles, dtype=np.float64).reshape((-1, 3, 3))
    if triangles.size == 0 or not np.isfinite(triangles).all():
        raise ValueError("Mesh must contain finite triangles")
    points = triangles.reshape((-1, 3))
    bounds = tuple((float(points[:, axis].min()), float(points[:, axis].max())) for axis in range(3))
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    area = float(np.linalg.norm(cross, axis=1).sum() * 0.5)

    # Two uses per undirected edge are required for a closed manifold shell.
    spans = np.asarray([high - low for low, high in bounds])
    # STL coordinates are commonly stored as float32. A scale-relative weld
    # tolerance accounts for a few ulps at larger model sizes without erasing
    # features in small meshes.
    quantization = max(1e-12, float(spans.max()) * 1e-7)
    quantized = np.rint((points - points[0]) / quantization).astype(np.int64).reshape((-1, 3, 3))
    edges = {}
    for triangle in quantized:
        for first, second in ((0, 1), (1, 2), (2, 0)):
            a, b = tuple(triangle[first]), tuple(triangle[second])
            key = (a, b) if a < b else (b, a)
            count, direction = edges.get(key, (0, 0))
            edges[key] = (count + 1, direction + (1 if a < b else -1))
    if any(count != 2 or direction != 0 for count, direction in edges.values()):
        return MeshMeasurements(area, None, None, bounds)

    origin = points.mean(axis=0)
    shifted = triangles - origin
    signed = np.einsum("ij,ij->i", shifted[:, 0], np.cross(shifted[:, 1], shifted[:, 2])) / 6.0
    total = float(signed.sum())
    if abs(total) <= max(1e-24, float(np.prod(spans)) * 1e-12):
        return MeshMeasurements(area, None, None, bounds)
    centroids = origin + shifted.sum(axis=1) / 4.0
    center = tuple(float(value) for value in (signed[:, None] * centroids).sum(axis=0) / total)
    return MeshMeasurements(area, abs(total), center, bounds)


def transform_triangles(triangles: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    linear, offset = matrix[:3, :3], matrix[:3, 3]
    out = triangles.astype(np.float64) @ linear.T + offset
    if np.linalg.det(linear) < 0:  # mirrored: swap two vertices so normals stay outward
        out = out[:, [0, 2, 1], :]
    return out.astype(np.float32)


def transform_normals(normals: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    linear = matrix[:3, :3]
    out = normals.astype(np.float64) @ np.linalg.inv(linear)  # inverse-transpose
    lengths = np.linalg.norm(out, axis=1, keepdims=True)
    return (out / np.where(lengths > _EPS, lengths, 1.0)).astype(np.float32)


def circular_array(
    count: int,
    total_angle: float = 360.0,
    axis: str = "Z",
    center=(0.0, 0.0, 0.0),
    rotate_copies: bool = True,
    pivot=None,
):
    """Matrices for a circular array. 360 deg spreads evenly (no duplicate at the end).

    rotate_copies=False keeps each copy's orientation and moves only its base
    point (`pivot`, world coordinates, required in that mode) along the circle.
    """
    if count < 1:
        raise ValueError("count must be >= 1")
    if not rotate_copies and pivot is None:
        raise ValueError("pivot is required when rotate_copies is False")
    full = abs(abs(total_angle) - 360.0) < _EPS
    step = total_angle / count if full or count == 1 else total_angle / (count - 1)
    matrices = []
    for k in range(count):
        m = rotation(axis, step * k, center)
        if not rotate_copies:
            p = np.asarray(pivot, dtype=float)
            m = translation((m @ np.append(p, 1.0))[:3] - p)
        matrices.append(m)
    return matrices


def rectangular_array(nx: int, ny: int, nz: int, dx: float, dy: float, dz: float):
    if min(nx, ny, nz) < 1:
        raise ValueError("counts must be >= 1")
    return [translation((i * dx, j * dy, k * dz)) for k in range(nz) for j in range(ny) for i in range(nx)]


def _add_section_segment(first, second, target, *, count_coplanar=False):
    a, b = np.asarray(first), np.asarray(second)
    if np.linalg.norm(a - b) <= _EPS:
        return
    ka, kb = tuple(np.rint(a / 1e-5).astype(np.int64)), tuple(np.rint(b / 1e-5).astype(np.int64))
    key = (ka, kb) if ka < kb else (kb, ka)
    if count_coplanar:
        target[key] = (target[key][0] + 1, target[key][1]) if key in target else (1, (a, b))
    else:
        target[key] = (a, b)


def _section_triangle(triangle, distances, coplanar_edges, segments):
    on_plane = np.flatnonzero(distances == 0.0)
    if len(on_plane) == 3:
        for first, second in ((0, 1), (1, 2), (2, 0)):
            _add_section_segment(triangle[first], triangle[second], coplanar_edges, count_coplanar=True)
        return
    if len(on_plane) == 2:
        _add_section_segment(triangle[on_plane[0]], triangle[on_plane[1]], segments)
        return
    hits = [triangle[index] for index in on_plane]
    for first, second in ((0, 1), (1, 2), (2, 0)):
        d0, d1 = distances[first], distances[second]
        if d0 * d1 < 0:
            hits.append(triangle[first] + d0 / (d0 - d1) * (triangle[second] - triangle[first]))
    if len(hits) == 2:
        _add_section_segment(hits[0], hits[1], segments)


def section(triangles: np.ndarray, axis: str, offset: float) -> np.ndarray:
    """Intersect triangles with the plane axis=offset. Returns (M,2,3) line segments."""
    triangles = np.asarray(triangles, dtype=np.float64).reshape((-1, 3, 3))
    coordinate = _AXES[axis.upper()]
    coplanar_edges = {}
    segments = {}
    for triangle in triangles:
        distances = triangle[:, coordinate] - offset
        distances[np.abs(distances) < _EPS] = 0.0
        _section_triangle(triangle, distances, coplanar_edges, segments)
    for key, (count, edge) in coplanar_edges.items():
        if count % 2:
            segments.setdefault(key, edge)
    return np.asarray(list(segments.values()), dtype=np.float32).reshape((-1, 2, 3))


def _inside_plane(distance, keep_positive):
    return distance >= -_EPS if keep_positive else distance <= _EPS


def _clip_triangle(triangle, coordinate, offset, keep_positive):
    if np.all(np.abs(triangle[:, coordinate] - offset) <= _EPS):
        # A source facet on the cutting plane already is the cap for this side.
        return [triangle], None
    polygon = []
    intersections = []
    for index in range(3):
        first = triangle[index]
        second = triangle[(index + 1) % 3]
        d0, d1 = first[coordinate] - offset, second[coordinate] - offset
        inside0, inside1 = _inside_plane(d0, keep_positive), _inside_plane(d1, keep_positive)
        if inside0:
            polygon.append(first)
        if inside0 != inside1:
            point = first + d0 / (d0 - d1) * (second - first)
            polygon.append(point)
            intersections.append(point)
    clipped = []
    if len(polygon) >= 3:
        for index in range(1, len(polygon) - 1):
            candidate = np.asarray((polygon[0], polygon[index], polygon[index + 1]))
            if np.linalg.norm(np.cross(candidate[1] - candidate[0], candidate[2] - candidate[0])) > _EPS:
                clipped.append(candidate)
    cut = (intersections[0], intersections[1]) if len(intersections) == 2 else None
    return clipped, cut


def _point_key(point, quantization):
    return tuple(np.rint(np.asarray(point) / quantization).astype(np.int64))


def _section_loops(segments, quantization):
    points, adjacency = {}, {}
    for first, second in segments:
        a, b = _point_key(first, quantization), _point_key(second, quantization)
        if a == b:
            continue
        points[a], points[b] = first, second
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    if any(len(neighbors) != 2 for neighbors in adjacency.values()):
        return []
    remaining = {tuple(sorted((a, b))) for a, neighbors in adjacency.items() for b in neighbors}
    loops = []
    while remaining:
        edge = next(iter(remaining))
        start, current = edge
        loop = [start]
        while True:
            remaining.discard(tuple(sorted((loop[-1], current))))
            next_points = adjacency[current] - {loop[-1]}
            next_point = next(iter(next_points))
            loop.append(current)
            if next_point == start:
                remaining.discard(tuple(sorted((current, start))))
                break
            current = next_point
        if len(loop) >= 3:
            loops.append(np.asarray([points[key] for key in loop], dtype=np.float64))
    return loops


def _project_section_loop(loop, axis):
    # Cyclic coordinate pairs keep the projected normal aligned with +axis.
    plane_axes = {"X": (1, 2), "Y": (2, 0), "Z": (0, 1)}[axis]
    return loop[:, plane_axes]


def _signed_area_2d(points):
    return float(np.sum(points[:, 0] * np.roll(points[:, 1], -1) - np.roll(points[:, 0], -1) * points[:, 1]))


def _point_in_polygon(point, polygon):
    inside = False
    x, y = point
    for first, second in zip(polygon, np.roll(polygon, -1, axis=0)):
        if (first[1] > y) != (second[1] > y):
            crossing_x = (second[0] - first[0]) * (y - first[1]) / (second[1] - first[1]) + first[0]
            inside ^= x < crossing_x
    return inside


def _normalize_section_loop(loop, axis, quantization):
    """Drop only adjacent duplicate vertices before passing a ring to earcut."""
    loop = np.asarray(loop, dtype=np.float64)
    projected = _project_section_loop(loop, axis)
    if len(projected) < 3:
        return None
    kept = [0]
    for index in range(1, len(projected)):
        if np.linalg.norm(projected[index] - projected[kept[-1]]) > quantization:
            kept.append(index)
    if len(kept) > 1 and np.linalg.norm(projected[kept[0]] - projected[kept[-1]]) <= quantization:
        kept.pop()
    if len(kept) < 3:
        return None
    normalized = loop[kept]
    area = _signed_area_2d(_project_section_loop(normalized, axis))
    if abs(area) <= max(_EPS, quantization**2 * 1e-2):
        return None
    return normalized


def _restore_ring_boundary_vertices(indices, vertices, tolerance):
    """Split earcut boundary edges at collinear contour vertices it omits."""
    used = np.zeros(len(vertices), dtype=bool)
    used[indices] = True
    unused = np.flatnonzero(~used)
    if unused.size == 0:
        return indices.reshape((-1, 3))

    triangles = []
    for source in indices.reshape((-1, 3)):
        pending = [source]
        while pending:
            triangle = pending.pop()
            split = False
            for first_index, second_index, opposite_index in (
                (0, 1, 2),
                (1, 2, 0),
                (2, 0, 1),
            ):
                first, second = vertices[triangle[first_index]], vertices[triangle[second_index]]
                direction = second - first
                length_squared = float(np.dot(direction, direction))
                if length_squared <= tolerance**2:
                    continue
                candidates = vertices[unused] - first
                parameters = candidates @ direction / length_squared
                distances = np.abs(direction[0] * candidates[:, 1] - direction[1] * candidates[:, 0]) / np.sqrt(
                    length_squared
                )
                on_edge = (parameters > 1e-12) & (parameters < 1.0 - 1e-12) & (distances <= tolerance)
                if not np.any(on_edge):
                    continue
                selected = unused[on_edge]
                order = np.argsort(parameters[on_edge])
                chain = [int(triangle[first_index]), *selected[order].tolist(), int(triangle[second_index])]
                selected_set = set(selected.tolist())
                unused = np.asarray([index for index in unused if int(index) not in selected_set], dtype=np.int64)
                pending.extend(
                    np.asarray((chain[index], chain[index + 1], int(triangle[opposite_index])), dtype=np.uint32)
                    for index in range(len(chain) - 1)
                )
                split = True
                break
            if not split:
                triangles.append(triangle)
    return np.asarray(triangles, dtype=np.uint32).reshape((-1, 3))


def _triangulate_polygon_with_holes(outer_loop, hole_loops, axis, offset, keep_positive):
    """Triangulate one outer section ring and its holes with mapbox-earcut."""
    plane_axes = {"X": (1, 2), "Y": (2, 0), "Z": (0, 1)}[axis]
    rings = [outer_loop, *hole_loops]
    projected_rings = [_project_section_loop(loop, axis) for loop in rings]
    vertices = np.ascontiguousarray(np.concatenate(projected_rings), dtype=np.float64)
    ring_ends = np.cumsum([len(ring) for ring in projected_rings], dtype=np.uint32)
    indices = mapbox_earcut.triangulate_float64(vertices, ring_ends)
    if indices.size == 0:
        return []
    tolerance = max(float(np.ptp(vertices, axis=0).max()) * 1e-10, 1e-12)
    indices = _restore_ring_boundary_vertices(indices, vertices, tolerance)

    points = np.empty((len(vertices), 3), dtype=np.float64)
    points[:, plane_axes] = vertices
    points[:, _AXES[axis]] = offset
    triangles = points[indices]
    normal_sign = -1.0 if keep_positive else 1.0
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    reverse = normals[:, _AXES[axis]] * normal_sign < 0.0
    triangles[reverse] = triangles[reverse][:, (0, 2, 1)]
    return triangles


def _cap_triangles(segments, axis, offset, keep_positive, quantization):
    loops = [
        normalized
        for loop in _section_loops(segments, quantization)
        if (normalized := _normalize_section_loop(loop, axis, quantization)) is not None
    ]
    projected = [_project_section_loop(loop, axis) for loop in loops]
    parents = []
    for index, polygon in enumerate(projected):
        containers = [
            other
            for other, candidate in enumerate(projected)
            if other != index and _point_in_polygon(polygon[0], candidate)
        ]
        parents.append(
            min(containers, key=lambda other: abs(_signed_area_2d(projected[other]))) if containers else None
        )
    cap = []
    for index, parent in enumerate(parents):
        depth = 0
        ancestor = parent
        while ancestor is not None:
            depth += 1
            ancestor = parents[ancestor]
        if depth % 2:
            continue
        holes = [loops[child] for child, candidate_parent in enumerate(parents) if candidate_parent == index]
        cap.extend(_triangulate_polygon_with_holes(loops[index], holes, axis, offset, keep_positive))
    return cap


def clip_mesh(triangles: np.ndarray, axis: str, offset: float, keep_positive: bool = True) -> np.ndarray:
    """Keep one side of an axis-aligned section plane and cap closed contours."""
    source = np.asarray(triangles, dtype=np.float64).reshape((-1, 3, 3))
    coordinate = _AXES[axis.upper()]
    surface, cut_segments = [], []
    for triangle in source:
        clipped, cut = _clip_triangle(triangle, coordinate, offset, keep_positive)
        surface.extend(clipped)
        if cut is not None:
            cut_segments.append(cut)
    if source.size == 0:
        return np.empty((0, 3, 3), dtype=np.float32)
    points = source.reshape((-1, 3))
    spans = np.ptp(points, axis=0)
    quantization = min(1e-5, max(1e-12, float(spans.max()) * 1e-6))
    cap = _cap_triangles(cut_segments, axis.upper(), offset, keep_positive, quantization)
    if cap:
        surface.extend(cap)
    return np.asarray(surface, dtype=np.float32).reshape((-1, 3, 3))
