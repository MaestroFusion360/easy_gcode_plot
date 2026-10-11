"""Actual OpenGL context for GPU stock regression tests."""

import pytest
from OpenGL import GL
from PyQt6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat
from PyQt6.QtWidgets import QApplication

from app.ui.plot.milling_stock_gpu import GpuStock


@pytest.fixture(scope="session")
def stock_gl_context():
    app = QApplication.instance() or QApplication([])
    fmt = QSurfaceFormat()
    fmt.setVersion(4, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create() or not context.makeCurrent(surface):
        pytest.skip("OpenGL context is unavailable")
    version = tuple(int(GL.glGetIntegerv(key)) for key in (GL.GL_MAJOR_VERSION, GL.GL_MINOR_VERSION))
    if version < (4, 3):
        pytest.skip("GPU stock requires OpenGL 4.3")
    yield context, surface, app
    context.doneCurrent()
    surface.destroy()


@pytest.fixture
def gpu_stock(stock_gl_context):
    context, surface, _app = stock_gl_context
    assert context.makeCurrent(surface)
    gpu = GpuStock()
    gpu.initialize(context)
    yield gpu
    context.makeCurrent(surface)
    GL.glUseProgram(0)
    GL.glBindVertexArray(0)
    gpu.destroy()
    context.doneCurrent()
