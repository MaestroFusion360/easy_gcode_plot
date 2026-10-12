"""GPU milling stock overlay; worker threads publish trajectories, never meshes."""

from threading import Event
from time import monotonic

from OpenGL import GL
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QOpenGLContext
from pyqtgraph.opengl.GLGraphicsItem import GLGraphicsItem

from app.ui.plot.milling_stock_gpu import GpuStock, prepare_frame


class MillingStockOverlayItem(GLGraphicsItem):
    snapshotRequested = pyqtSignal(object, object, object)
    renderFailed = pyqtSignal(object, object)

    def __init__(self, stock_color="#4fa7a0", cut_color="#b8a879"):
        super().__init__()
        self.setGLOptions(
            {
                GL.GL_DEPTH_TEST: True,
                GL.GL_BLEND: False,
                GL.GL_CULL_FACE: False,
                "glDepthFunc": (GL.GL_LEQUAL,),
                "glDepthMask": (True,),
            }
        )
        self._stock = QColor(stock_color).getRgb()
        self._cut = QColor(cut_color).getRgb()
        self._rapid = QColor("#e52626").getRgb()
        self.surface_error, self.edge_error = 0.01, 0.05
        self._timeline = None
        self._frame = None
        self._gpu = GpuStock()
        self._failure = None
        self.snapshotRequested.connect(self._snapshot_on_gui)

    def set_quality(self, surface_error, edge_error):
        if surface_error <= 0 or edge_error <= 0:
            raise ValueError("Stock tolerances must be positive")
        self.surface_error, self.edge_error = float(surface_error), float(edge_error)

    def set_colors(self, stock, removed):
        self._stock, self._cut = QColor(stock).getRgb(), QColor(removed).getRgb()
        self.update()

    def set_playing(self, playing):
        pass

    @property
    def mesh_tiles(self):
        return {}

    @property
    def buffer_bytes(self):
        return self._gpu.bytes

    @property
    def memory_budget(self):
        return self._gpu.memory_budget

    def clear(self):
        self._failure = None
        self._frame = None
        self._timeline = None
        view = self.view()
        if view is not None and view.context() is self._gpu.context:
            view.makeCurrent()
            try:
                self._gpu.destroy()
            finally:
                view.doneCurrent()
        self.update()

    def set_frame(self, timeline):
        frame = self.build_frame(timeline)
        self.apply_frame(timeline, frame, frame.revision)

    def build_frame(self, timeline, cancelled=lambda: False):
        timeline.snapshot_reader = self._read_snapshot
        frame = prepare_frame(timeline, self.surface_error, self.edge_error, cancelled)
        self._gpu.validate_frame(frame)
        return frame

    def calculated_snapshot(self, timeline, *, cancelled=lambda: False):
        return self._read_snapshot(timeline, cancelled=cancelled, calculated=True)

    def _read_snapshot(self, timeline, *, cancelled=lambda: False, calculated=False):
        deadline = monotonic() + 10.0
        abandoned = Event()

        def check_cancelled():
            return abandoned.is_set() or cancelled() or monotonic() >= deadline

        result, ready = {"cancelled": check_cancelled}, Event()
        if calculated:
            result["frame"] = self._frame
        if cancelled():
            raise InterruptedError("Stock snapshot cancelled")
        if QThread.currentThread() is self.thread():
            self._snapshot_on_gui(timeline, result, ready)
        else:
            self.snapshotRequested.emit(timeline, result, ready)
            # A deleted Qt receiver or stopped GUI event loop must not strand
            # the exporting thread indefinitely.
            while not ready.wait(timeout=0.05):
                if check_cancelled():
                    abandoned.set()
                    break
        if cancelled():
            raise InterruptedError("Stock snapshot cancelled")
        if abandoned.is_set() or monotonic() >= deadline:
            raise TimeoutError("Timed out waiting for GPU stock snapshot on GUI thread")
        if "error" in result:
            raise result["error"]
        return result["snapshot"]

    @pyqtSlot(object, object, object)
    def _snapshot_on_gui(self, timeline, result, ready):
        try:
            cancelled = result["cancelled"]
            if cancelled():
                raise InterruptedError("Stock snapshot cancelled")
            view = self.view()
            if view is None or view.context() is None:
                raise ValueError("GPU stock view is unavailable")
            if "frame" in result:
                frame = result["frame"]
                key = None if frame is None else (frame.timeline, frame.surface_error, frame.edge_error)
                if (
                    frame is None
                    or frame.timeline is not timeline
                    or self._gpu.key != key
                    or self._gpu.count != frame.count
                ):
                    raise ValueError("Wait for the calculated stock frame to finish displaying before exporting.")
            else:
                frame = prepare_frame(timeline, self.surface_error, self.edge_error, cancelled)
            view.makeCurrent()
            try:
                if "frame" not in result:
                    self._gpu.initialize(view.context())
                    self._gpu.update(frame, cancelled=cancelled)
                if cancelled():
                    raise InterruptedError("Stock snapshot cancelled")
                snapshot = self._gpu.snapshot(timeline)
                if cancelled():
                    raise InterruptedError("Stock snapshot cancelled")
                result["snapshot"] = snapshot
            finally:
                GL.glUseProgram(0)
                GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
                view.doneCurrent()
        except Exception as exc:
            result["error"] = exc
        finally:
            ready.set()

    def apply_frame(self, timeline, tiles, revision):
        self._timeline = timeline
        self._frame = tiles
        timeline.acknowledge_frame(revision)
        self.update()

    def paint(self):
        frame = self._frame
        context = QOpenGLContext.currentContext()
        if frame is None or context is None or self._frame_error(frame) is not None:
            return
        program = int(GL.glGetIntegerv(GL.GL_CURRENT_PROGRAM))
        vao = int(GL.glGetIntegerv(GL.GL_VERTEX_ARRAY_BINDING))
        active = int(GL.glGetIntegerv(GL.GL_ACTIVE_TEXTURE))
        GL.glActiveTexture(GL.GL_TEXTURE0)
        texture = int(GL.glGetIntegerv(GL.GL_TEXTURE_BINDING_2D))
        storage = int(GL.glGetIntegerv(GL.GL_SHADER_STORAGE_BUFFER_BINDING))
        indexed_storage = int(GL.glGetIntegeri_v(GL.GL_SHADER_STORAGE_BUFFER_BINDING, 0))
        try:
            self._gpu.initialize(context)
            self._gpu.update(frame)
            self.setupGLState()
            self._gpu.draw(self.mvpMatrix(), (self._stock, self._cut, self._rapid))
        except Exception as exc:
            self._failure = ((frame.timeline, frame.surface_error, frame.edge_error), exc)
            self.renderFailed.emit(frame.timeline, exc)
        finally:
            GL.glUseProgram(program)
            GL.glBindVertexArray(vao)
            GL.glBindBufferBase(GL.GL_SHADER_STORAGE_BUFFER, 0, indexed_storage)
            GL.glBindBuffer(GL.GL_SHADER_STORAGE_BUFFER, storage)
            GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
            GL.glActiveTexture(active)

    def _frame_error(self, frame):
        if frame is not None and self._failure is not None:
            key, error = self._failure
            if key == (frame.timeline, frame.surface_error, frame.edge_error):
                return error
        return None
