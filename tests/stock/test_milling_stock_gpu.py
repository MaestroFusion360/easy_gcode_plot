"""GPU removal, replay and the visible closed stock boundary."""

import numpy as np
import pytest
from OpenGL import GL
from PyQt6.QtGui import QMatrix4x4, QVector3D
from PyQt6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat

from app.gcode.kernel import TraceMotion
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


def render_stock(gpu, camera, target):
    fmt = QOpenGLFramebufferObjectFormat()
    fmt.setAttachment(QOpenGLFramebufferObject.Attachment.CombinedDepthStencil)
    framebuffer = QOpenGLFramebufferObject(64, 64, fmt)
    assert framebuffer.bind()
    GL.glViewport(0, 0, 64, 64)
    GL.glEnable(GL.GL_DEPTH_TEST)
    GL.glDepthMask(True)
    GL.glDisable(GL.GL_BLEND)
    GL.glDisable(GL.GL_CULL_FACE)
    GL.glClearColor(0, 0, 0, 0)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
    projection, view = QMatrix4x4(), QMatrix4x4()
    projection.ortho(-3, 3, -3, 3, 0.1, 20)
    view.lookAt(QVector3D(*camera), QVector3D(*target), QVector3D(0, 1, 0))
    gpu.draw(projection * view, ((0, 255, 0, 255), (255, 0, 0, 255), (0, 0, 255, 255)))
    pixels = np.empty((64, 64, 4), dtype=np.uint8)
    GL.glReadPixels(0, 0, 64, 64, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixels)
    framebuffer.release()
    return pixels


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
