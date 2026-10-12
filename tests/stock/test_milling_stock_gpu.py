"""GPU removal, replay and the visible closed stock boundary."""

import numpy as np
import pytest
from OpenGL import GL
from PyQt6.QtGui import QImage, QMatrix4x4, QVector3D
from PyQt6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat

from app.gcode.kernel import TraceMotion, execute
from app.gcode.stock import MillingStockSpec, MillingStockTimeline
from app.ui.plot.milling_stock_gpu import prepare_frame

SPEC = MillingStockSpec(-2, 2, -2, 2, -2, 0)
FLAT = {"type": "mill_flat", "diameter": 2, "length": 10}
BALL = {"type": "mill_ball", "diameter": 2, "length": 10}


def plunge(z, move=1):
    return TraceMotion(move, 0, 1, 0, z, start_y=0, end_y=0, tool="T1")


def publish(gpu, timeline, count, edge_error=0.2):
    timeline.set_motion_count(count)
    gpu.update(prepare_frame(timeline, 0.01, edge_error, lambda: False))
    return gpu.snapshot(timeline)


def test_flat_plunge_removes_only_its_footprint_without_cpu_height_map(gpu_stock):
    timeline = MillingStockTimeline([plunge(-1)], SPEC, {"T1": FLAT})
    stock = publish(gpu_stock, timeline, 1)
    x = SPEC.x_min + np.arange(stock.nx + 1) * stock.dx
    y = SPEC.y_min + np.arange(stock.ny + 1) * stock.dy
    yy, xx = np.meshgrid(y, x, indexing="ij")
    inside = xx * xx + yy * yy <= 1
    np.testing.assert_allclose(stock.height[inside], -1, atol=1e-6)
    np.testing.assert_array_equal(stock.height[~inside], 0)
    assert not hasattr(timeline, "height")
    assert not hasattr(timeline, "rapid")


def test_ball_plunge_has_analytic_spherical_tip(gpu_stock):
    timeline = MillingStockTimeline([plunge(-1)], SPEC, {"T1": BALL})
    stock = publish(gpu_stock, timeline, 1)
    x = SPEC.x_min + np.arange(stock.nx + 1) * stock.dx
    y = SPEC.y_min + np.arange(stock.ny + 1) * stock.dy
    yy, xx = np.meshgrid(y, x, indexing="ij")
    radius2 = xx * xx + yy * yy
    inside = radius2 < 1
    np.testing.assert_allclose(stock.height[inside], -np.sqrt(1 - radius2[inside]), atol=2e-6)


def test_gpu_rewind_restores_material_and_forward_replay_is_identical(gpu_stock):
    timeline = MillingStockTimeline([plunge(-1), plunge(-1.5)], SPEC, {"T1": FLAT})
    finished = publish(gpu_stock, timeline, 2)
    initial = publish(gpu_stock, timeline, 0)
    np.testing.assert_array_equal(initial.height, 0)
    repeated = publish(gpu_stock, timeline, 2)
    np.testing.assert_array_equal(repeated.height, finished.height)


def test_rapid_damage_survives_deeper_feed(gpu_stock):
    timeline = MillingStockTimeline([plunge(-0.5, move=0), plunge(-1)], SPEC, {"T1": FLAT})
    rapid = publish(gpu_stock, timeline, 1)
    feed = publish(gpu_stock, timeline, 2)
    assert np.any(rapid.rapid)
    np.testing.assert_array_equal(feed.rapid, rapid.rapid)


def test_accuracy_refines_gpu_state_without_advancing_replay(gpu_stock):
    timeline = MillingStockTimeline([plunge(-1)], SPEC, {"T1": BALL})
    coarse = publish(gpu_stock, timeline, 1, edge_error=0.5)
    fine = publish(gpu_stock, timeline, 1, edge_error=0.1)
    assert fine.dx < coarse.dx and fine.dy < coarse.dy
    assert timeline.motion_count == 1
    assert fine.height.min() == pytest.approx(-1, abs=0.002)


def render_stock(gpu, camera, target, *, far=20, size=64):
    fmt = QOpenGLFramebufferObjectFormat()
    fmt.setAttachment(QOpenGLFramebufferObject.Attachment.CombinedDepthStencil)
    framebuffer = QOpenGLFramebufferObject(size, size, fmt)
    assert framebuffer.bind()
    GL.glViewport(0, 0, size, size)
    GL.glEnable(GL.GL_DEPTH_TEST)
    GL.glDepthMask(True)
    GL.glDisable(GL.GL_BLEND)
    GL.glDisable(GL.GL_CULL_FACE)
    GL.glClearColor(0, 0, 0, 0)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
    projection, view = QMatrix4x4(), QMatrix4x4()
    projection.ortho(-3, 3, -3, 3, 0.1, far)
    view.lookAt(QVector3D(*camera), QVector3D(*target), QVector3D(0, 1, 0))
    gpu.draw(projection * view, ((0, 255, 0, 255), (255, 0, 0, 255), (0, 0, 255, 255)))
    pixels = np.empty((size, size, 4), dtype=np.uint8)
    GL.glReadPixels(0, 0, size, size, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixels)
    framebuffer.release()
    return pixels


@pytest.mark.parametrize("tool", [FLAT, {**FLAT, "type": "mill_bull", "cornerRadius": 0.2}])
def test_diagonal_cut_wall_has_consistent_lighting(gpu_stock, tmp_path, tool):
    motion = TraceMotion(1, -4, -1, 4, -1, start_y=-3, end_y=3, tool="T1")
    timeline = MillingStockTimeline([motion], SPEC, {"T1": tool})
    publish(gpu_stock, timeline, 1, edge_error=0.1)
    pixels = render_stock(gpu_stock, (-6, 8, 6), (0, 0, -0.5), size=512)
    # Keep a rendered artifact for diagnosing driver-specific failures.
    image = QImage(pixels.data, 512, 512, QImage.Format.Format_RGBA8888).mirrored()
    image.save(str(tmp_path / "wall.png"))
    projection, view = QMatrix4x4(), QMatrix4x4()
    projection.ortho(-3, 3, -3, 3, 0.1, 20)
    view.lookAt(QVector3D(-6, 8, 6), QVector3D(0, 0, -0.5), QVector3D(0, 1, 0))
    matrix = projection * view
    # Sample parallel to the straight wall, away from its floor and top edge.
    points = [matrix.map(QVector3D(0.6 + 0.8 * s, -0.8 + 0.6 * s, -0.5)) for s in np.linspace(-1, 1, 300)]
    wall = np.array([pixels[int((p.y() + 1) * 256), int((p.x() + 1) * 256)] for p in points])
    assert np.all(wall[:, 3] == 255)
    assert not np.any(wall[:, 1:3])
    assert np.ptp(wall[:, 0]) <= 8


@pytest.mark.parametrize("camera,target", [((0, 0, -8), (0, 0, -1)), ((8, 0, -1), (0, 0, -1))])
def test_box_bottom_and_sides_are_opaque_uniform_stock_color(gpu_stock, camera, target):
    timeline = MillingStockTimeline([plunge(-1)], SPEC, {"T1": BALL})
    publish(gpu_stock, timeline, 1)
    pixels = render_stock(gpu_stock, camera, target)
    face = pixels[28:36, 28:36]
    assert np.all(face[..., 3] == 255)
    assert np.all(face[..., 0] == 0) and np.all(face[..., 2] == 0)
    assert np.ptp(face[..., 1]) == 0


def test_fully_removed_stock_does_not_leave_a_bottom_cap(gpu_stock):
    tool = {**FLAT, "diameter": 20}
    timeline = MillingStockTimeline([plunge(-3)], SPEC, {"T1": tool})
    stock = publish(gpu_stock, timeline, 1)
    np.testing.assert_array_equal(stock.height, SPEC.z_min)
    pixels = render_stock(gpu_stock, (0, 0, -8), (0, 0, -1))
    assert not np.any(pixels[..., 3])


@pytest.mark.parametrize("far", [20, 200000])
@pytest.mark.parametrize("camera", [(0, 0, 8), (6, 0, 8)])
def test_machined_floor_remains_opaque_with_distant_clip_plane(gpu_stock, far, camera):
    timeline = MillingStockTimeline([plunge(-1)], SPEC, {"T1": FLAT})
    stock = publish(gpu_stock, timeline, 1, edge_error=0.05)
    assert stock.height.min() == pytest.approx(-1)
    pixels = render_stock(gpu_stock, camera, (0, 0, -1), far=far)
    floor = pixels[30:34, 30:34]
    assert np.all(floor[..., 3] == 255)
    assert np.all(floor[..., 0] > 0)
    assert not np.any(floor[..., 1:3])


def test_unchanged_gpu_frame_reuses_detached_snapshot(gpu_stock):
    timeline = MillingStockTimeline([plunge(-1)], SPEC, {"T1": FLAT})
    first = publish(gpu_stock, timeline, 1)
    assert publish(gpu_stock, timeline, 1) is first
    rewound = publish(gpu_stock, timeline, 0)
    assert rewound is not first
    np.testing.assert_array_equal(first.height.min(), -1)
    np.testing.assert_array_equal(rewound.height, 0)


def test_toolchange_fixture_contour_has_visible_calculated_floor(gpu_stock, fixture_text):
    source = fixture_text("milling/fanuc/toolchange.nc").split("N325", 1)[0] + "\nM30\n%"
    result = execute(source, "fanuc_mill")
    assert result.ok and result.complete
    tools = {"T1": {**FLAT, "diameter": 50}, "T2": {**FLAT, "diameter": 8}}
    timeline = MillingStockTimeline(result.motions, MillingStockSpec(-105, 105, -65, 65, -5, 0), tools)
    stock = publish(gpu_stock, timeline, len(result.motions), edge_error=0.25)
    x, y = round((79 - stock.spec.x_min) / stock.dx), round((-7 - stock.spec.y_min) / stock.dy)
    assert stock.height[y, x] == pytest.approx(-1, abs=1e-5)
    pixels = render_stock(gpu_stock, (79, -7, 8), (79, -7, -1), far=200000)
    floor = pixels[30:34, 30:34]
    assert np.all(floor[..., 3] == 255) and np.all(floor[..., 0] > 0)
    assert not np.any(floor[..., 1:3])
