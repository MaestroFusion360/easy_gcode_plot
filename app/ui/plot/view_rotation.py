"""World-axis camera rotations independent of CNC geometry and machine axes."""

import math

from PyQt6.QtGui import QQuaternion, QVector3D

AXES = {"X": QVector3D(1, 0, 0), "Y": QVector3D(0, 1, 0), "Z": QVector3D(0, 0, 1)}


def rotate_camera(view, axis, angle):
    """Rotate the camera around a world axis, retaining center and projection."""
    if axis not in AXES or not math.isfinite(angle):
        raise ValueError("Camera rotation requires X/Y/Z and a finite angle")
    current = QQuaternion.fromRotationMatrix(view.viewMatrix().normalMatrix())
    delta = QQuaternion.fromAxisAndAngle(AXES[axis], angle % 360)
    # GLViewWidget stores world-to-camera rotation; camera orbit applies
    # the inverse world rotation on the right of that transform.
    rotation = (current * delta.conjugated()).normalized()
    view.opts["rotationMethod"] = "quaternion"
    view.setCameraPosition(rotation=rotation)


def camera_plane(view):
    """Return the coordinate plane facing the camera, or None for oblique views."""
    rotation = QQuaternion.fromRotationMatrix(view.viewMatrix().normalMatrix())
    normal = rotation.conjugated().rotatedVector(QVector3D(0, 0, 1))
    components = (abs(normal.x()), abs(normal.y()), abs(normal.z()))
    dominant = max(range(3), key=components.__getitem__)
    if any(value > 1e-6 for index, value in enumerate(components) if index != dominant):
        return None
    return ("yz", "xz", "xy")[dominant]
