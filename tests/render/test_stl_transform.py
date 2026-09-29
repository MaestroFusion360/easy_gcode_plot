from __future__ import annotations

import numpy as np
import pytest

from app.ui.plot import stl_transform
from app.ui.plot.stl import StlMesh
from app.ui.plot.stl_transform import StlObject, circular_array, clip_mesh, measure_mesh, rectangular_array, section

# Cap construction is an internal geometry helper exercised directly here.
# pylint: disable=protected-access


def _cube(size=10.0):
    p = np.asarray(
        [
            (0, 0, 0),
            (size, 0, 0),
            (size, size, 0),
            (0, size, 0),
            (0, 0, size),
            (size, 0, size),
            (size, size, size),
            (0, size, size),
        ],
        dtype=np.float32,
    )
    faces = np.asarray(
        [
            (0, 2, 1),
            (0, 3, 2),
            (4, 5, 6),
            (4, 6, 7),
            (0, 1, 5),
            (0, 5, 4),
            (1, 2, 6),
            (1, 6, 5),
            (2, 3, 7),
            (2, 7, 6),
            (3, 0, 4),
            (3, 4, 7),
        ],
        dtype=np.int32,
    )
    triangles = p[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    return StlMesh(triangles, normals.astype(np.float32), ((0.0, size), (0.0, size), (0.0, size)))


def _signed_volume(triangles):
    return np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6.0


def _section_segments(rings, axis, offset):
    plane_axes = {"X": (1, 2), "Y": (2, 0), "Z": (0, 1)}[axis]
    coordinate = {"X": 0, "Y": 1, "Z": 2}[axis]
    segments = []
    for ring in rings:
        points = np.zeros((len(ring), 3), dtype=np.float64)
        points[:, plane_axes] = ring
        points[:, coordinate] = offset
        segments.extend(np.stack((points, np.roll(points, -1, axis=0)), axis=1))
    return np.asarray(segments)


def _cap_area(cap):
    cross = np.cross(cap[:, 1] - cap[:, 0], cap[:, 2] - cap[:, 0])
    return float(np.linalg.norm(cross, axis=1).sum() / 2.0)


def _hollow_cube():
    outer = _cube(4.0).triangles
    inner = _cube(2.0).triangles + np.asarray((1.0, 1.0, 1.0), dtype=np.float32)
    inner = inner[:, (0, 2, 1), :]
    triangles = np.concatenate((outer, inner))
    points = triangles.reshape((-1, 3))
    bounds = tuple((float(points[:, axis].min()), float(points[:, axis].max())) for axis in range(3))
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    return StlMesh(triangles, normals.astype(np.float32), bounds)


def test_stl_object_transform_is_non_destructive_and_pivot_stays_fixed():
    mesh = _cube()
    source = mesh.triangles.copy()
    obj = StlObject(mesh).set_pivot("center").move_pivot_to((20.0, 30.0, 40.0))
    rotated = obj.rotate("Z", 90.0)

    assert rotated.world_pivot() == pytest.approx((20.0, 30.0, 40.0))
    assert mesh.triangles == pytest.approx(source)


def test_mirror_keeps_positive_winding_volume():
    obj = StlObject(_cube()).set_pivot("center")
    original_volume = _signed_volume(obj.world_triangles())
    mirrored_volume = _signed_volume(obj.mirrored("X").world_triangles())

    assert original_volume > 0.0
    assert mirrored_volume == pytest.approx(original_volume)


def test_arrays_have_expected_copy_positions_without_360_duplicate():
    circular = circular_array(4, 360.0, "Z", center=(0.0, 0.0, 0.0))
    point = np.asarray((10.0, 0.0, 0.0, 1.0))
    positions = np.asarray([(matrix @ point)[:3] for matrix in circular])

    assert len(circular) == 4
    np.testing.assert_allclose(positions, ((10, 0, 0), (0, 10, 0), (-10, 0, 0), (0, -10, 0)), atol=1e-8)
    assert len(rectangular_array(2, 3, 1, 10.0, 20.0, 0.0)) == 6


def test_axis_section_of_cube_has_perimeter_40_and_outside_is_empty():
    triangles = StlObject(_cube()).world_triangles()
    middle = section(triangles, "Z", 5.0)
    outside = section(triangles, "Z", 20.0)
    perimeter = np.linalg.norm(middle[:, 1] - middle[:, 0], axis=1).sum()

    assert perimeter == pytest.approx(40.0)
    assert outside.shape == (0, 2, 3)


def test_section_along_cube_face_keeps_boundary_without_internal_diagonal():
    triangles = StlObject(_cube()).world_triangles()
    for offset in (0.0, 10.0):
        contour = section(triangles, "Z", offset)
        assert len(contour) == 4
        assert np.linalg.norm(contour[:, 1] - contour[:, 0], axis=1).sum() == pytest.approx(40.0)


def test_mesh_measurements_follow_transform_and_reject_open_volume():
    obj = StlObject(_cube()).set_pivot("center").scaled(2.0).move_pivot_to((20.0, 30.0, 40.0))
    measurement = measure_mesh(obj.world_triangles())
    assert measurement.area == pytest.approx(2400.0)
    assert measurement.volume == pytest.approx(8000.0)
    assert measurement.center_of_mass == pytest.approx((20.0, 30.0, 40.0))
    assert np.asarray(measurement.bounds) == pytest.approx(np.asarray(((10, 30), (20, 40), (30, 50))))

    open_mesh = measure_mesh(_cube().triangles[:-1])
    assert open_mesh.area > 0
    assert open_mesh.volume is None
    assert open_mesh.center_of_mass is None

    tiny = measure_mesh(StlObject(_cube()).scaled(1e-6).world_triangles())
    assert tiny.volume == pytest.approx(1e-15, rel=1e-6)


@pytest.mark.parametrize("axis", ("X", "Y", "Z"))
def test_midplane_sections_have_consistent_outward_caps(axis):
    source = _cube(1.0).triangles
    cut = clip_mesh(source, axis, 0.5, keep_positive=True)

    assert measure_mesh(cut).volume == pytest.approx(0.5)


@pytest.mark.parametrize("axis", ("X", "Y", "Z"))
@pytest.mark.parametrize(("keep_positive", "expected_volume"), ((True, 0.75), (False, 0.25)))
def test_section_keeps_requested_half_and_closes_cap(axis, keep_positive, expected_volume):
    cut = clip_mesh(_cube(1.0).triangles, axis, 0.25, keep_positive=keep_positive)
    coordinate = {"X": 0, "Y": 1, "Z": 2}[axis]
    bounds = measure_mesh(cut).bounds[coordinate]

    assert bounds == pytest.approx((0.25, 1.0) if keep_positive else (0.0, 0.25))
    assert measure_mesh(cut).volume == pytest.approx(expected_volume)


@pytest.mark.parametrize("axis", ("X", "Y", "Z"))
def test_section_on_minimum_outer_face_keeps_closed_source_mesh(axis):
    source = _cube(1.0).triangles
    cut = clip_mesh(source, axis, 0.0, keep_positive=True)
    measured = measure_mesh(cut)

    assert len(cut) == 12
    assert measured.area == pytest.approx(6.0)
    assert measured.volume == pytest.approx(1.0)


def test_section_cap_preserves_hole_in_hollow_closed_mesh():
    source = _hollow_cube().triangles
    cut = clip_mesh(source, "Z", 2.0, keep_positive=True)
    cap = cut[np.all(np.isclose(cut[:, :, 2], 2.0), axis=1)]
    cap_area = np.linalg.norm(np.cross(cap[:, 1] - cap[:, 0], cap[:, 2] - cap[:, 0]), axis=1).sum() / 2

    assert cap_area == pytest.approx(12.0)
    assert measure_mesh(cut).volume == pytest.approx(28.0)


@pytest.mark.parametrize(
    ("polygon", "expected_area"),
    (
        (np.asarray(((0, 0), (6, 0), (6, 4), (0, 4))), 24.0),
        (np.asarray(((0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4))), 7.0),
    ),
    ids=("convex", "concave"),
)
def test_section_cap_earcut_triangulates_convex_and_concave_contours(polygon, expected_area):
    cap = stl_transform._cap_triangles(_section_segments((polygon,), "Z", 3.0), "Z", 3.0, True, 1e-6)

    assert _cap_area(np.asarray(cap)) == pytest.approx(expected_area)


def test_section_cap_keeps_holes_empty_and_supports_multiple_outers():
    outer = np.asarray(((0, 0), (10, 0), (10, 10), (0, 10)), dtype=float)
    hole = np.asarray(((3, 3), (7, 3), (7, 7), (3, 7)), dtype=float)[::-1]
    second_outer = np.asarray(((20, 0), (25, 0), (25, 5), (20, 5)), dtype=float)
    cap = np.asarray(
        stl_transform._cap_triangles(_section_segments((outer, hole, second_outer), "Z", 2.0), "Z", 2.0, True, 1e-6)
    )

    centroids = cap[:, :, :2].mean(axis=1)
    in_hole = np.all((centroids > 3.0) & (centroids < 7.0), axis=1)
    assert not np.any(in_hole)
    assert _cap_area(cap) == pytest.approx(109.0)


@pytest.mark.parametrize("axis", ("X", "Y", "Z"))
@pytest.mark.parametrize(("keep_positive", "normal_sign"), ((True, -1.0), (False, 1.0)))
def test_section_cap_axis_and_keep_side_set_outward_normal(axis, keep_positive, normal_sign):
    square = np.asarray(((0, 0), (4, 0), (4, 3), (0, 3)), dtype=float)
    cap = np.asarray(
        stl_transform._cap_triangles(_section_segments((square,), axis, 1.5), axis, 1.5, keep_positive, 1e-6)
    )
    normals = np.cross(cap[:, 1] - cap[:, 0], cap[:, 2] - cap[:, 0])
    coordinate = {"X": 0, "Y": 1, "Z": 2}[axis]

    assert _cap_area(cap) == pytest.approx(12.0)
    assert np.all(normals[:, coordinate] * normal_sign > 0.0)


def test_large_polygon_with_hole_uses_mapbox_earcut(monkeypatch):
    original = stl_transform.mapbox_earcut.triangulate_float64
    calls = []

    def tracked(vertices, ring_ends):
        calls.append((len(vertices), ring_ends.copy()))
        return original(vertices, ring_ends)

    monkeypatch.setattr(stl_transform.mapbox_earcut, "triangulate_float64", tracked)
    angles_outer = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
    angles_hole = np.linspace(0.0, 2.0 * np.pi, 180, endpoint=False)
    outer = np.column_stack((10.0 * np.cos(angles_outer), 10.0 * np.sin(angles_outer)))
    hole = np.column_stack((2.0 * np.cos(angles_hole), 2.0 * np.sin(angles_hole)))[::-1]
    cap = stl_transform._cap_triangles(_section_segments((outer, hole), "Y", 0.0), "Y", 0.0, True, 1e-6)

    assert calls and calls[0][0] == 540
    np.testing.assert_array_equal(calls[0][1], (360, 540))
    assert _cap_area(np.asarray(cap)) == pytest.approx(96.0 * np.pi, rel=2e-4)


@pytest.mark.parametrize("factor", (1e-6, 1e6))
def test_repeated_scale_rejects_mesh_precision_loss(factor):
    obj = StlObject(_cube(10.0)).set_pivot("center")
    successful = 0
    for _ in range(12):
        try:
            obj = obj.scaled(factor)
        except ValueError:
            break
        successful += 1
        assert measure_mesh(obj.world_triangles()).volume is not None

    assert successful < 12
