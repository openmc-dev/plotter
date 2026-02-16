import math
import numpy as np


class OrbitCamera:
    def __init__(self):
        self.distance = 15.0
        self.azimuth = math.radians(45.0)
        self.elevation = math.radians(30.0)
        self.target = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        self.world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        self.fov = 45.0

        self.rotate_speed = 0.005
        self.pan_speed = 1.0
        self.zoom_speed = 0.1
        self.min_distance = 1.0

    def position(self):
        cos_e = math.cos(self.elevation)
        sin_e = math.sin(self.elevation)
        cos_a = math.cos(self.azimuth)
        sin_a = math.sin(self.azimuth)
        x = self.target[0] + self.distance * cos_e * cos_a
        y = self.target[1] + self.distance * cos_e * sin_a
        z = self.target[2] + self.distance * sin_e
        return np.array([x, y, z], dtype=np.float64)

    def view_vectors(self):
        pos = self.position()
        forward = self.target - pos
        forward = forward / np.linalg.norm(forward)
        up_ref = self.world_up
        if abs(np.dot(forward, up_ref)) > 0.999:
            up_ref = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        right = np.cross(forward, up_ref)
        right = right / np.linalg.norm(right)
        up = np.cross(right, forward)
        up = up / np.linalg.norm(up)
        return forward, right, up

    def orbit(self, dx, dy):
        self.azimuth -= dx * self.rotate_speed
        self.elevation -= dy * self.rotate_speed
        max_e = math.radians(89.0)
        self.elevation = max(-max_e, min(max_e, self.elevation))

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
        self.azimuth = math.radians(45.0)
        self.elevation = math.radians(35.264)

    def set_axis_view(self, axis, negative=False):
        axis = axis.lower()
        if axis == "x":
            self.azimuth = math.pi if negative else 0.0
            self.elevation = 0.0
        elif axis == "y":
            self.azimuth = -math.pi / 2.0 if negative else math.pi / 2.0
            self.elevation = 0.0
        elif axis == "z":
            self.azimuth = 0.0
            self.elevation = -math.pi / 2.0 if negative else math.pi / 2.0

    def set_speeds(self, rotate_speed=None, pan_speed=None, zoom_speed=None):
        if rotate_speed is not None:
            self.rotate_speed = float(rotate_speed)
        if pan_speed is not None:
            self.pan_speed = float(pan_speed)
        if zoom_speed is not None:
            self.zoom_speed = float(zoom_speed)
