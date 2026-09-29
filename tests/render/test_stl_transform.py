from __future__ import annotations

import numpy as np
import pytest

from app.ui.plot.stl import StlMesh
from app.ui.plot.stl_transform import StlObject, circular_array, measure_mesh, rectangular_array, section


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
