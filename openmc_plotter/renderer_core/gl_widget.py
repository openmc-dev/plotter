import time
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import (
    glBindTexture,
    glClear,
    glClearColor,
    glDeleteTextures,
    glDisable,
    glEnable,
    glGenTextures,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPixelStorei,
    glTexImage2D,
    glTexParameteri,
    glTexSubImage2D,
    glViewport,
    glBegin,
    glEnd,
    glTexCoord2f,
    glVertex2f,
    GL_COLOR_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_MODELVIEW,
    GL_PROJECTION,
    GL_QUADS,
    GL_RGB,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_LINEAR,
    GL_UNSIGNED_BYTE,
    GL_UNPACK_ALIGNMENT,
)

from camera import OrbitCamera


class GLPlotWidget(QOpenGLWidget):
    def __init__(self, plotter, parent=None):
        super().__init__(parent)
        self._plotter = plotter
        self._camera = OrbitCamera()
        self._texture = None
        self._dirty = True
        self._last_pos = None
        self._buttons = set()
        self._render_mode = "final"
        self._interactive_scale = 0.35
        self._min_frame_interval = 1.0 / 15.0
        self._last_render_time = 0.0
        self._render_size = None

        self._idle_timer = QtCore.QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._request_final_render)

        self._throttle_timer = QtCore.QTimer(self)
        self._throttle_timer.setSingleShot(True)
        self._throttle_timer.timeout.connect(self._do_update)

        self._light_follows_camera = True
        self._light_control_mode = False
        self._light_distance = self._camera.distance
        self._light_azimuth = self._camera.azimuth
        self._light_elevation = self._camera.elevation

        self._help_overlay = QtWidgets.QFrame(self)
        self._help_overlay.setVisible(False)
        self._help_overlay.setFocusPolicy(QtCore.Qt.StrongFocus)
        self._help_overlay.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self._help_overlay.setStyleSheet(
            "QFrame { background-color: rgba(0, 0, 0, 200); color: white; }"
        )
        self._help_overlay.installEventFilter(self)

        overlay_layout = QtWidgets.QVBoxLayout(self._help_overlay)
        overlay_layout.setContentsMargins(24, 24, 24, 24)

        title = QtWidgets.QLabel("OpenMC Renderer Controls", self._help_overlay)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        overlay_layout.addWidget(title)

        help_text = QtWidgets.QTextBrowser(self._help_overlay)
        help_text.setFrameStyle(QtWidgets.QFrame.NoFrame)
        help_text.setOpenExternalLinks(False)
        help_text.setStyleSheet("background: transparent; color: white;")
        help_text.setHtml(
            """
<b>Camera Controls</b><br>
Left drag: Orbit camera<br>
Right drag: Pan camera<br>
Mouse wheel: Zoom<br>
Camera presets: Iso, +/-X, +/-Y, +/-Z buttons<br>
<br>
<b>Light Controls</b><br>
Light follows camera: toggles light to camera position<br>
Light control mode: left drag rotates light, right drag changes distance<br>
Mouse wheel changes light distance when light control mode is active<br>
<br>
<b>Display</b><br>
Color by: switch between material and cell coloring<br>
Visibility list: toggle per material/cell<br>
Color swatch: edit per material/cell color<br>
Save PNG: Ctrl+S / Cmd+S<br>
Copy image: Ctrl+C / Cmd+C or right-click<br>
"""
        )
        overlay_layout.addWidget(help_text, 1)

        hint = QtWidgets.QLabel("Press ? or Esc to close", self._help_overlay)
        hint.setStyleSheet("color: #dddddd;")
        overlay_layout.addWidget(hint)

        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def minimumSizeHint(self):
        return QtCore.QSize(400, 300)

    def sizeHint(self):
        return QtCore.QSize(900, 700)

    def initializeGL(self):
        glClearColor(0.05, 0.05, 0.06, 1.0)
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)

        self._texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self._texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        self._dirty = True

    def resizeGL(self, width, height):
        glViewport(0, 0, width, height)
        if width > 0 and height > 0:
            self._render_mode = "interactive"
            self._dirty = True
            self._idle_timer.start(250)
            self._request_redraw()
        self._help_overlay.setGeometry(self.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._help_overlay.setGeometry(self.rect())

    def eventFilter(self, obj, event):
        if obj == self._help_overlay:
            if event.type() in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.KeyPress):
                self.toggle_help_overlay()
                return True
        return super().eventFilter(obj, event)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT)

        if self._dirty:
            self._sync_plotter_camera()
            width, height = self._current_render_size()
            self._ensure_plotter_size(width, height)
            image = self._plotter.create_image()
            self._upload_texture(image)
            self._dirty = False
            self._last_render_time = time.monotonic()

        self._draw_textured_quad()

    def _sync_plotter_camera(self):
        pos = self._camera.position()
        _, _, up = self._camera.view_vectors()
        if self._light_follows_camera:
            self._sync_light_from_camera()
            light_pos = pos
        else:
            light_pos = self._light_position()
        self._plotter.set_camera(
            position=pos,
            look_at=self._camera.target,
            up=up,
            fov=self._camera.fov,
            light_position=light_pos,
        )

    def _upload_texture(self, image):
        if self._texture is None:
            return
        image = np.ascontiguousarray(image, dtype=np.uint8)
        height, width, _ = image.shape
        glBindTexture(GL_TEXTURE_2D, self._texture)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGB,
            width,
            height,
            0,
            GL_RGB,
            GL_UNSIGNED_BYTE,
            image,
        )

    def _current_render_size(self):
        width = max(1, self.width())
        height = max(1, self.height())
        if self._render_mode == "interactive":
            width = max(64, int(width * self._interactive_scale))
            height = max(64, int(height * self._interactive_scale))
        return width, height

    def _ensure_plotter_size(self, width, height):
        if self._render_size != (width, height):
            self._plotter.set_pixels(width, height)
            self._render_size = (width, height)

    def _do_update(self):
        self.update()

    def _request_redraw(self, force=False):
        if force:
            self.update()
            return
        now = time.monotonic()
        elapsed = now - self._last_render_time
        if elapsed >= self._min_frame_interval and not self._throttle_timer.isActive():
            self.update()
            return
        if not self._throttle_timer.isActive():
            delay = max(0.0, self._min_frame_interval - elapsed)
            self._throttle_timer.start(int(delay * 1000))

    def _request_interactive_render(self):
        self._render_mode = "interactive"
        self._dirty = True
        self._idle_timer.start(250)
        self._request_redraw()

    def _request_final_render(self):
        self._render_mode = "final"
        self._dirty = True
        self._request_redraw(force=True)

    def request_final_render(self):
        self._request_final_render()

    def toggle_help_overlay(self):
        if self._help_overlay.isVisible():
            self._help_overlay.hide()
        else:
            self._help_overlay.setGeometry(self.rect())
            self._help_overlay.show()
            self._help_overlay.raise_()
            self._help_overlay.setFocus(QtCore.Qt.ActiveWindowFocusReason)

    def _capture_frame(self):
        if not self.isValid():
            return QtGui.QImage()
        if self._render_mode != "final" or self._dirty:
            self._render_mode = "final"
            self._dirty = True
            self.repaint()
        return self.grabFramebuffer()

    def copy_screenshot_to_clipboard(self):
        image = self._capture_frame()
        if image.isNull():
            QtWidgets.QMessageBox.warning(
                self,
                "Copy Image",
                "Failed to capture the current frame.",
            )
            return
        QtWidgets.QApplication.clipboard().setImage(image)

    def save_screenshot(self):
        image = self._capture_frame()
        if image.isNull():
            QtWidgets.QMessageBox.warning(
                self,
                "Save PNG",
                "Failed to capture the current frame.",
            )
            return

        default_dir = QtCore.QStandardPaths.writableLocation(
            QtCore.QStandardPaths.PicturesLocation
        )
        if not default_dir:
            default_dir = QtCore.QDir.homePath()
        timestamp = QtCore.QDateTime.currentDateTime().toString(
            "yyyyMMdd_HHmmss"
        )
        default_name = f"openmc_render_{timestamp}.png"
        default_path = QtCore.QDir(default_dir).filePath(default_name)

        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Rendered Image",
            default_path,
            "PNG Images (*.png)",
        )
        if not filename:
            return
        if not filename.lower().endswith(".png"):
            filename += ".png"
        if not image.save(filename, "PNG"):
            QtWidgets.QMessageBox.warning(
                self,
                "Save PNG",
                f"Failed to save image to:\n{filename}",
            )

    def contextMenuEvent(self, event):
        if self._help_overlay.isVisible():
            event.accept()
            return

        menu = QtWidgets.QMenu(self)
        copy_action = menu.addAction("Copy Image")
        save_action = menu.addAction("Save Image As...")
        selected_action = menu.exec(event.globalPos())

        if selected_action == copy_action:
            self.copy_screenshot_to_clipboard()
        elif selected_action == save_action:
            self.save_screenshot()
        event.accept()

    def set_light_follows_camera(self, enabled):
        self._light_follows_camera = bool(enabled)
        if enabled:
            self._sync_light_from_camera()
        self._request_final_render()

    def set_light_control_mode(self, enabled):
        self._light_control_mode = bool(enabled)
        self.setCursor(QtCore.Qt.CrossCursor if self._light_control_mode else QtCore.Qt.ArrowCursor)

    def _light_position(self):
        cos_e = np.cos(self._light_elevation)
        sin_e = np.sin(self._light_elevation)
        cos_a = np.cos(self._light_azimuth)
        sin_a = np.sin(self._light_azimuth)
        x = self._camera.target[0] + self._light_distance * cos_e * cos_a
        y = self._camera.target[1] + self._light_distance * cos_e * sin_a
        z = self._camera.target[2] + self._light_distance * sin_e
        return np.array([x, y, z], dtype=np.float64)

    def _sync_light_from_camera(self):
        self._light_distance = self._camera.distance
        self._light_azimuth = self._camera.azimuth
        self._light_elevation = self._camera.elevation

    def _draw_textured_quad(self):
        if self._texture is None:
            return
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, 1, 0, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glBindTexture(GL_TEXTURE_2D, self._texture)
        glBegin(GL_QUADS)
        # OpenMC image rows are top-to-bottom; OpenGL texture coordinates are
        # bottom-to-top. Flip the texture vertically to preserve axis direction.
        glTexCoord2f(0.0, 1.0)
        glVertex2f(0.0, 0.0)
        glTexCoord2f(1.0, 1.0)
        glVertex2f(1.0, 0.0)
        glTexCoord2f(1.0, 0.0)
        glVertex2f(1.0, 1.0)
        glTexCoord2f(0.0, 0.0)
        glVertex2f(0.0, 1.0)
        glEnd()

    def mousePressEvent(self, event):
        if self._help_overlay.isVisible():
            event.accept()
            return
        self._last_pos = event.position()
        self._buttons.add(event.button())
        event.accept()

    def set_isometric_view(self):
        self._camera.set_isometric_view()
        if self._light_follows_camera:
            self._sync_light_from_camera()
        self._request_final_render()

    def set_axis_view(self, axis, negative=False):
        self._camera.set_axis_view(axis, negative=negative)
        if self._light_follows_camera:
            self._sync_light_from_camera()
        self._request_final_render()

    def set_camera_speeds(self, rotate=None, pan=None, zoom=None):
        self._camera.set_speeds(rotate_speed=rotate, pan_speed=pan, zoom_speed=zoom)

    def mouseReleaseEvent(self, event):
        if self._help_overlay.isVisible():
            event.accept()
            return
        if event.button() in self._buttons:
            self._buttons.remove(event.button())
        if not self._buttons:
            self._request_final_render()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._help_overlay.isVisible():
            event.accept()
            return
        if self._last_pos is None:
            self._last_pos = event.position()
            return

        dx = event.position().x() - self._last_pos.x()
        dy = event.position().y() - self._last_pos.y()

        if self._light_control_mode:
            if QtCore.Qt.LeftButton in self._buttons:
                self._light_azimuth += dx * 0.005
                self._light_elevation += dy * 0.005
                max_e = np.radians(89.0)
                self._light_elevation = max(-max_e, min(max_e, self._light_elevation))
                self._request_interactive_render()
            elif QtCore.Qt.RightButton in self._buttons:
                self._light_distance *= 1.0 + (dy * 0.01)
                if self._light_distance < 1.0:
                    self._light_distance = 1.0
                self._request_interactive_render()
        else:
            if QtCore.Qt.LeftButton in self._buttons:
                self._camera.orbit(dx, dy)
                self._request_interactive_render()
            elif QtCore.Qt.RightButton in self._buttons:
                self._camera.pan(dx, dy, self.height())
                self._request_interactive_render()

        self._last_pos = event.position()

    def wheelEvent(self, event):
        if self._help_overlay.isVisible():
            event.accept()
            return
        delta = event.angleDelta().y() / 120.0
        if self._light_control_mode and not self._light_follows_camera:
            self._light_distance *= 1.0 - delta * 0.1
            if self._light_distance < 1.0:
                self._light_distance = 1.0
            self._request_interactive_render()
        else:
            self._camera.zoom(delta)
            self._request_interactive_render()

    def keyPressEvent(self, event):
        key = event.key()
        if event.matches(QtGui.QKeySequence.Save):
            self.save_screenshot()
            event.accept()
            return
        if event.matches(QtGui.QKeySequence.Copy):
            self.copy_screenshot_to_clipboard()
            event.accept()
            return
        if key == QtCore.Qt.Key_F1 or (
            key == QtCore.Qt.Key_Slash and event.modifiers() & QtCore.Qt.ShiftModifier
        ):
            self.toggle_help_overlay()
            event.accept()
            return
        if key == QtCore.Qt.Key_Escape and self._help_overlay.isVisible():
            self.toggle_help_overlay()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if self._texture is not None:
            glDeleteTextures(1, [self._texture])
            self._texture = None
        super().closeEvent(event)
