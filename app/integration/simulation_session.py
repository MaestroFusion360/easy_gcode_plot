"""Deliver simulation requests to an already running GUI through local Qt IPC."""

import hashlib
import json
import sys
from pathlib import Path

from PyQt6.QtCore import QDir, QLockFile, QObject, QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from app.integration.minicad_bundle import read_bundle


def session_name():
    executable = str(Path(sys.executable).resolve()).casefold()
    return "easy-gcode-plot-simulate-" + hashlib.sha256(executable.encode()).hexdigest()[:24]


def forward_simulation(file, language, bundle, *, name=None):
    """Return False only when no running GUI is accepting requests."""
    socket = QLocalSocket()
    socket.connectToServer(name or session_name())
    if not socket.waitForConnected(500):
        return False
    request = {
        "file": str(Path(file).resolve()),
        "language": language,
        "bundle": str(bundle.manifest) if bundle is not None and bundle.manifest is not None else None,
    }
    socket.write((json.dumps(request) + "\n").encode())
    socket.flush()
    if not socket.waitForReadyRead(5000):
        raise RuntimeError("The running simulator did not acknowledge the request")
    reply = bytes(socket.readAll()).decode().strip()
    socket.disconnectFromServer()
    if reply != "ok":
        raise RuntimeError(reply or "The running simulator rejected the request")
    return True


class SimulationSession(QObject):
    """A user-local listener that queues validated requests in the GUI thread."""

    def __init__(self, callback, *, name=None):
        super().__init__()
        self.callback = callback
        self.name = name or session_name()
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._accept)
        self.connections = {}
        self.lock = QLockFile(str(Path(QDir.tempPath()) / (self.name + ".lock")))
        self.lock.setStaleLockTime(0)

    def listen(self):
        # Windows named pipes allow multiple servers with the same name.
        # Own a lock before listening so a second GUI cannot steal requests.
        if not self.lock.tryLock(0):
            return False
        QLocalServer.removeServer(self.name)
        if self.server.listen(self.name):
            return True
        self.lock.unlock()
        return False

    def close(self):
        self.server.close()
        self.lock.unlock()

    def _accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.connections[socket] = bytearray()
            socket.readyRead.connect(lambda socket=socket: self._read(socket))
            socket.disconnected.connect(lambda socket=socket: self._closed(socket))
            self._read(socket)

    def _closed(self, socket):
        self.connections.pop(socket, None)
        socket.deleteLater()

    def _read(self, socket):
        data = self.connections[socket]
        data.extend(bytes(socket.readAll()))
        if len(data) > 65536:
            socket.abort()
            return
        if b"\n" not in data:
            return
        try:
            request = json.loads(data.decode())
            file = Path(request["file"]).resolve(strict=True)
            language = request["language"]
            if language not in ("fanuc_mill", "fanuc_turn"):
                raise ValueError("Invalid simulation language")
            bundle = read_bundle(request["bundle"]) if request.get("bundle") else None
            if bundle is not None and bundle.nc != file:
                raise ValueError("NC file must match bundle manifest")
        except (ValueError, OSError, KeyError, TypeError) as exc:
            socket.write((str(exc) + "\n").encode())
        else:
            socket.write(b"ok\n")
            QTimer.singleShot(0, lambda: self.callback(file, language, bundle))
        socket.flush()
        socket.disconnectFromServer()
