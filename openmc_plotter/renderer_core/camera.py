import math
import numpy as np


class OrbitCamera:
    _EPS = 1.0e-12

    def __init__(self):
        self.distance = 15.0
        self.target = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        self.world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        self.fov = 45.0

        self.rotate_speed = 0.005
        self.pan_speed = 1.0
        self.zoom_speed = 0.1
        self.min_distance = 1.0

        self._orientation = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self._set_from_spherical(math.radians(45.0), math.radians(30.0))

    @staticmethod
    def _normalize(vec):
        norm = np.linalg.norm(vec)
        if norm <= OrbitCamera._EPS:
            return vec
        return vec / norm

    @staticmethod
    def _quat_normalize(quat):
        norm = np.linalg.norm(quat)
        if norm <= OrbitCamera._EPS:
            return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        return quat / norm

    @staticmethod
    def _quat_conjugate(quat):
        return np.array([quat[0], -quat[1], -quat[2], -quat[3]], dtype=np.float64)

    @staticmethod
    def _quat_multiply(q1, q2):
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array(
            [
                w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
                w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            ],
            dtype=np.float64,
        )

    @staticmethod
    def _quat_from_axis_angle(axis, angle):
        axis = np.asarray(axis, dtype=np.float64)
        axis_norm = np.linalg.norm(axis)
        if axis_norm <= OrbitCamera._EPS or abs(angle) <= OrbitCamera._EPS:
            return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        axis = axis / axis_norm
        half = 0.5 * angle
        s = math.sin(half)
        return np.array([math.cos(half), axis[0] * s, axis[1] * s, axis[2] * s], dtype=np.float64)

    @staticmethod
    def _quat_rotate(quat, vec):
        q_vec = np.array([0.0, vec[0], vec[1], vec[2]], dtype=np.float64)
        rotated = OrbitCamera._quat_multiply(
            OrbitCamera._quat_multiply(quat, q_vec),
            OrbitCamera._quat_conjugate(quat),
        )
        return rotated[1:]

    @staticmethod
    def _quat_from_matrix(matrix):
        m = np.asarray(matrix, dtype=np.float64)
        trace = m[0, 0] + m[1, 1] + m[2, 2]
        if trace > 0.0:
            s = math.sqrt(trace + 1.0) * 2.0
            w = 0.25 * s
            x = (m[2, 1] - m[1, 2]) / s
            y = (m[0, 2] - m[2, 0]) / s
            z = (m[1, 0] - m[0, 1]) / s
        elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
            s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
            w = (m[2, 1] - m[1, 2]) / s
            x = 0.25 * s
            y = (m[0, 1] + m[1, 0]) / s
            z = (m[0, 2] + m[2, 0]) / s
        elif m[1, 1] > m[2, 2]:
            s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
            w = (m[0, 2] - m[2, 0]) / s
            x = (m[0, 1] + m[1, 0]) / s
            y = 0.25 * s
            z = (m[1, 2] + m[2, 1]) / s
        else:
            s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
            w = (m[1, 0] - m[0, 1]) / s
            x = (m[0, 2] + m[2, 0]) / s
            y = (m[1, 2] + m[2, 1]) / s
            z = 0.25 * s
        quat = np.array([w, x, y, z], dtype=np.float64)
        return OrbitCamera._quat_normalize(quat)

    def _offset_direction(self):
        return self._normalize(self._quat_rotate(self._orientation, np.array([1.0, 0.0, 0.0], dtype=np.float64)))

    def _spherical_angles(self):
        offset = self._offset_direction()
        azimuth = math.atan2(offset[1], offset[0])
        elevation = math.atan2(offset[2], math.hypot(offset[0], offset[1]))
        return azimuth, elevation

    def _set_from_spherical(self, azimuth, elevation):
        cos_e = math.cos(elevation)
        offset = np.array(
            [
                cos_e * math.cos(azimuth),
                cos_e * math.sin(azimuth),
                math.sin(elevation),
            ],
            dtype=np.float64,
        )
        self._set_from_forward(-offset, up_hint=self.world_up)

    def _set_from_forward(self, forward, up_hint=None):
        forward = self._normalize(np.asarray(forward, dtype=np.float64))
        if np.linalg.norm(forward) <= self._EPS:
            return

        if up_hint is None:
            up_hint = self.world_up
        up_ref = self._normalize(np.asarray(up_hint, dtype=np.float64))
        right = np.cross(forward, up_ref)
        if np.linalg.norm(right) <= self._EPS:
            alt_up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
            if abs(np.dot(forward, alt_up)) > 0.95:
                alt_up = np.array([1.0, 0.0, 0.0], dtype=np.float64)
            right = np.cross(forward, alt_up)

        right = self._normalize(right)
        up = self._normalize(np.cross(right, forward))
        offset = -forward
        basis = np.column_stack((offset, right, up))
        self._orientation = self._quat_from_matrix(basis)

    @property
    def azimuth(self):
        azimuth, _ = self._spherical_angles()
        return azimuth

    @azimuth.setter
    def azimuth(self, value):
        _, elevation = self._spherical_angles()
        self._set_from_spherical(float(value), elevation)

    @property
    def elevation(self):
        _, elevation = self._spherical_angles()
        return elevation

    @elevation.setter
    def elevation(self, value):
        azimuth, _ = self._spherical_angles()
        self._set_from_spherical(azimuth, float(value))

    def position(self):
        return self.target + self.distance * self._offset_direction()

    def view_vectors(self):
        offset = self._offset_direction()
        forward = -offset
        right = self._normalize(self._quat_rotate(self._orientation, np.array([0.0, 1.0, 0.0], dtype=np.float64)))
        up = self._normalize(self._quat_rotate(self._orientation, np.array([0.0, 0.0, 1.0], dtype=np.float64)))
        # Re-orthonormalize to avoid numerical drift after many updates.
        right = self._normalize(np.cross(forward, up))
        up = self._normalize(np.cross(right, forward))
        return forward, right, up

    def orbit(self, dx, dy):
        yaw = -dx * self.rotate_speed
        pitch = -dy * self.rotate_speed
        if abs(yaw) > self._EPS:
            q_yaw = self._quat_from_axis_angle(self.world_up, yaw)
            self._orientation = self._quat_normalize(
                self._quat_multiply(q_yaw, self._orientation)
            )
        if abs(pitch) > self._EPS:
            _, right, _ = self.view_vectors()
            q_pitch = self._quat_from_axis_angle(right, pitch)
            self._orientation = self._quat_normalize(
                self._quat_multiply(q_pitch, self._orientation)
            )

    def pan(self, dx, dy, viewport_height):
        if viewport_height <= 0:
            return
        _, right, up = self.view_vectors()
        scale = 2.0 * self.distance * math.tan(math.radians(self.fov) * 0.5) / viewport_height
        # Keep horizontal pan behavior, but invert vertical pan to match the
        # rendered image orientation in the embedded widget.
        self.target += (-right * dx + up * dy) * scale * self.pan_speed

    def zoom(self, delta):
        self.distance *= (1.0 - delta * self.zoom_speed)
        if self.distance < self.min_distance:
            self.distance = self.min_distance

    def set_isometric_view(self):
        self._set_from_spherical(math.radians(45.0), math.radians(35.264))

    def set_axis_view(self, axis, negative=False):
        axis = axis.lower()
        offset = None
        if axis == "x":
            offset = np.array([-1.0, 0.0, 0.0], dtype=np.float64) if negative else np.array([1.0, 0.0, 0.0], dtype=np.float64)
        elif axis == "y":
            offset = np.array([0.0, -1.0, 0.0], dtype=np.float64) if negative else np.array([0.0, 1.0, 0.0], dtype=np.float64)
        elif axis == "z":
            offset = np.array([0.0, 0.0, -1.0], dtype=np.float64) if negative else np.array([0.0, 0.0, 1.0], dtype=np.float64)
        if offset is None:
            return

        forward = -offset
        up_hint = self.world_up
        if axis == "z":
            # Avoid ambiguous world-up alignment in top/bottom views.
            up_hint = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        self._set_from_forward(forward, up_hint=up_hint)

    def set_speeds(self, rotate_speed=None, pan_speed=None, zoom_speed=None):
        if rotate_speed is not None:
            self.rotate_speed = float(rotate_speed)
        if pan_speed is not None:
            self.pan_speed = float(pan_speed)
        if zoom_speed is not None:
            self.zoom_speed = float(zoom_speed)
