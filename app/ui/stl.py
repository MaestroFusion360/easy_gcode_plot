"""Small dependency-free ASCII/binary STL reader and geometry helpers."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MAX_STL_TRIANGLES = 2_000_000
_NORMAL_EPSILON = 1e-12
_BINARY_FACET_DTYPE = np.dtype(
    [
        ("normal", "<f4", (3,)),
        ("vertices", "<f4", (3, 3)),
        ("attribute_byte_count", "<u2"),
    ]
)


@dataclass(frozen=True)
class StlMesh:
    triangles: np.ndarray
    normals: np.ndarray
    bounds: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]

    @property
    def triangle_count(self) -> int:
        return int(self.triangles.shape[0])


def _normal(triangle: np.ndarray) -> np.ndarray:
    value = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
    length = float(np.linalg.norm(value))
    return value / length if length > _NORMAL_EPSILON else np.array((0.0, 0.0, 1.0), dtype=np.float32)


def _normalized_normals(triangles: np.ndarray, normals) -> np.ndarray:
    normal_array = np.asarray(normals, dtype=np.float32).reshape((-1, 3)).copy()
    if normal_array.shape[0] != triangles.shape[0]:
        raise ValueError("STL normal count does not match triangle count")

    lengths = np.linalg.norm(normal_array, axis=1)
    valid = np.isfinite(normal_array).all(axis=1) & (lengths > _NORMAL_EPSILON)
    if np.any(valid):
        normal_array[valid] /= lengths[valid, None]

    invalid = ~valid
    if np.any(invalid):
        fallback = np.cross(
            triangles[invalid, 1] - triangles[invalid, 0],
            triangles[invalid, 2] - triangles[invalid, 0],
        )
        fallback_lengths = np.linalg.norm(fallback, axis=1)
        usable = fallback_lengths > _NORMAL_EPSILON
        fallback[usable] /= fallback_lengths[usable, None]
        fallback[~usable] = (0.0, 0.0, 1.0)
        normal_array[invalid] = fallback

    return normal_array


def _mesh(triangles, normals) -> StlMesh:
    triangle_array = np.asarray(triangles, dtype=np.float32).reshape((-1, 3, 3))
    if triangle_array.size == 0:
        raise ValueError("STL contains no triangles")
    if not np.isfinite(triangle_array).all():
        raise ValueError("STL contains non-finite coordinates")

    normal_array = _normalized_normals(triangle_array, normals)
    points = triangle_array.reshape((-1, 3))
    bounds = tuple((float(points[:, axis].min()), float(points[:, axis].max())) for axis in range(3))
    return StlMesh(triangle_array, normal_array, bounds)


def _read_binary(data: bytes, count: int) -> StlMesh:
    if count > MAX_STL_TRIANGLES:
        raise ValueError(f"STL has too many triangles ({count:,})")
    expected = 84 + count * _BINARY_FACET_DTYPE.itemsize
    if expected > len(data):
        raise ValueError(f"Truncated binary STL: expected {expected} bytes, got {len(data)}")

    facets = np.frombuffer(data, dtype=_BINARY_FACET_DTYPE, count=count, offset=84)
    # Copy the two arrays we keep so the full source byte buffer can be released
    # immediately after read_stl() returns.
    triangles = np.ascontiguousarray(facets["vertices"])
    normals = np.ascontiguousarray(facets["normal"])
    return _mesh(triangles, normals)


def _read_ascii(data: bytes) -> StlMesh:
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("STL is neither valid binary nor ASCII") from exc
    triangles = []
    normals = []
    vertices = []
    current_normal = None
    for line_number, raw in enumerate(lines, 1):
        parts = raw.strip().split()
        if not parts:
            continue
        keyword = parts[0].lower()
        try:
            if keyword == "facet" and len(parts) >= 5 and parts[1].lower() == "normal":
                current_normal = tuple(float(value) for value in parts[2:5])
            elif keyword == "vertex" and len(parts) >= 4:
                vertices.append(tuple(float(value) for value in parts[1:4]))
                if len(vertices) == 3:
                    if len(triangles) >= MAX_STL_TRIANGLES:
                        raise ValueError(f"STL has more than {MAX_STL_TRIANGLES:,} triangles")
                    triangle = np.asarray(vertices, dtype=np.float32)
                    triangles.append(triangle)
                    normals.append(current_normal if current_normal is not None else _normal(triangle))
                    vertices = []
                    current_normal = None
        except ValueError as exc:
            raise ValueError(f"Invalid ASCII STL number on line {line_number}") from exc
    if vertices:
        raise ValueError("Incomplete triangle at end of ASCII STL")
    return _mesh(triangles, normals)


def read_stl(path: str | Path) -> StlMesh:
    """Read an STL mesh, choosing binary by its authoritative byte length."""
    data = Path(path).read_bytes()
    if len(data) >= 84:
        count = struct.unpack_from("<I", data, 80)[0]
        expected = 84 + count * _BINARY_FACET_DTYPE.itemsize
        header_is_ascii = data[:80].lstrip().lower().startswith(b"solid")
        if expected == len(data) or (not header_is_ascii and expected <= len(data)):
            return _read_binary(data, count)
    return _read_ascii(data)


def stl_face_colors(
    mesh: StlMesh,
    *,
    base_color=(0.69, 0.69, 0.69),
    ambient: float = 0.22,
    light_direction=(0.3, 0.6, 1.0),
) -> np.ndarray:
    """Create stable two-sided flat lighting from the authoritative STL normals."""
    light = np.asarray(light_direction, dtype=np.float32)
    length = float(np.linalg.norm(light))
    if length <= _NORMAL_EPSILON:
        raise ValueError("light_direction must be non-zero")
    light /= length
    # STL winding is not reliably consistent across exporters. Two-sided
    # lighting keeps incorrectly wound but otherwise valid faces readable.
    diffuse = np.abs(mesh.normals @ light)
    intensity = ambient + (1.0 - ambient) * diffuse
    base = np.asarray(base_color, dtype=np.float32)
    if base.shape != (3,) or not np.isfinite(base).all():
        raise ValueError("base_color must contain three finite RGB components")
    colors = np.empty((mesh.triangle_count, 4), dtype=np.float32)
    colors[:, :3] = np.clip(base[None, :] * intensity[:, None], 0.0, 1.0)
    colors[:, 3] = 1.0
    return colors


def stl_feature_edges(mesh: StlMesh, *, cos_threshold: float = 0.995, quantization: float = 1e-4) -> np.ndarray:
    """Return boundary and sharp edges while suppressing coplanar triangle diagonals."""
    if quantization <= 0:
        raise ValueError("quantization must be positive")
    edges = {}
    for triangle_index, triangle in enumerate(mesh.triangles):
        normal = mesh.normals[triangle_index]
        keys = [tuple(np.rint(vertex / quantization).astype(np.int64)) for vertex in triangle]
        base_index = triangle_index * 3
        for first, second in ((0, 1), (1, 2), (2, 0)):
            if keys[first] <= keys[second]:
                key = (keys[first], keys[second])
                indices = (base_index + first, base_index + second)
            else:
                key = (keys[second], keys[first])
                indices = (base_index + second, base_index + first)
            entry = edges.get(key)
            if entry is None:
                edges[key] = [indices, normal, 1, False]
            else:
                entry[2] += 1
                if float(np.dot(entry[1], normal)) < cos_threshold:
                    entry[3] = True

    selected = [entry[0] for entry in edges.values() if entry[2] == 1 or entry[3]]
    return np.asarray(selected, dtype=np.uint32).reshape((-1, 2))
