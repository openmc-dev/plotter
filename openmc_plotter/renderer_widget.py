from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import (QCheckBox, QComboBox, QColorDialog, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QSlider, QSplitter, QVBoxLayout,
                               QWidget)


class RendererWidget(QWidget):
    """Embedded OpenMC renderer with controls panel."""

    def __init__(self, plotter, gl_widget_cls, parent=None):
        super().__init__(parent)
        self.plotter = plotter
        self.gl_widget = gl_widget_cls(plotter, self)

        self._buildUi()
        self._connectSignals()
        self._initializeState()

    def _buildUi(self):
        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(QtCore.Qt.Horizontal, self)
        self.mainLayout.addWidget(self.splitter)

        viewerWidget = QWidget(self.splitter)
        viewerLayout = QVBoxLayout(viewerWidget)
        viewerLayout.setContentsMargins(0, 0, 0, 0)

        toolbarLayout = QHBoxLayout()
        self.saveButton = QPushButton("Save PNG", viewerWidget)
        self.controlsButton = QPushButton("Controls", viewerWidget)
        toolbarLayout.addWidget(self.saveButton)
        toolbarLayout.addWidget(self.controlsButton)
        toolbarLayout.addStretch()

        viewerLayout.addLayout(toolbarLayout)
        viewerLayout.addWidget(self.gl_widget)

        self.controlsWidget = QWidget(self.splitter)
        self.controlsWidget.setMinimumWidth(320)
        controlsLayout = QVBoxLayout(self.controlsWidget)
        controlsLayout.setContentsMargins(8, 8, 8, 8)

        modeLayout = QHBoxLayout()
        modeLayout.addWidget(QLabel("Color by:", self.controlsWidget))
        self.modeCombo = QComboBox(self.controlsWidget)
        self.modeCombo.addItem("Material", self.plotter.COLOR_BY_MATERIAL)
        self.modeCombo.addItem("Cell", self.plotter.COLOR_BY_CELL)
        modeLayout.addWidget(self.modeCombo, 1)
        controlsLayout.addLayout(modeLayout)

        cameraGroup = QGroupBox("Camera", self.controlsWidget)
        cameraLayout = QVBoxLayout(cameraGroup)

        presetLayout = QGridLayout()
        self.isoButton = QPushButton("Iso", cameraGroup)
        self.xPosButton = QPushButton("+X", cameraGroup)
        self.xNegButton = QPushButton("-X", cameraGroup)
        self.yPosButton = QPushButton("+Y", cameraGroup)
        self.yNegButton = QPushButton("-Y", cameraGroup)
        self.zPosButton = QPushButton("+Z", cameraGroup)
        self.zNegButton = QPushButton("-Z", cameraGroup)

        presetLayout.addWidget(self.isoButton, 0, 0, 1, 2)
        presetLayout.addWidget(self.xPosButton, 1, 0)
        presetLayout.addWidget(self.xNegButton, 1, 1)
        presetLayout.addWidget(self.yPosButton, 2, 0)
        presetLayout.addWidget(self.yNegButton, 2, 1)
        presetLayout.addWidget(self.zPosButton, 3, 0)
        presetLayout.addWidget(self.zNegButton, 3, 1)
        cameraLayout.addLayout(presetLayout)

        self.rotateSlider = self._makeScaledSlider(cameraLayout, "Rotate", 0.001, 0.02, 0.005)
        self.panSlider = self._makeScaledSlider(cameraLayout, "Pan", 0.2, 5.0, 1.0)
        self.zoomSlider = self._makeScaledSlider(cameraLayout, "Zoom", 0.02, 0.5, 0.1)
        controlsLayout.addWidget(cameraGroup)

        lightGroup = QGroupBox("Lighting", self.controlsWidget)
        lightLayout = QVBoxLayout(lightGroup)

        self.lightFollowCheckbox = QCheckBox("Light follows camera", lightGroup)
        self.lightFollowCheckbox.setChecked(True)
        lightLayout.addWidget(self.lightFollowCheckbox)

        self.lightControlCheckbox = QCheckBox("Light control mode", lightGroup)
        lightLayout.addWidget(self.lightControlCheckbox)

        diffuseLayout = QHBoxLayout()
        diffuseLayout.addWidget(QLabel("Diffuse", lightGroup))
        self.diffuseSlider = QSlider(QtCore.Qt.Horizontal, lightGroup)
        self.diffuseSlider.setRange(0, 100)
        self.diffuseSlider.setValue(10)
        self.diffuseValueLabel = QLabel("0.10", lightGroup)
        diffuseLayout.addWidget(self.diffuseSlider, 1)
        diffuseLayout.addWidget(self.diffuseValueLabel)
        lightLayout.addLayout(diffuseLayout)

        controlsLayout.addWidget(lightGroup)

        self.scrollArea = QScrollArea(self.controlsWidget)
        self.scrollArea.setWidgetResizable(True)
        self.scrollContainer = QWidget(self.scrollArea)
        self.visibilityLayout = QVBoxLayout(self.scrollContainer)
        self.visibilityLayout.setAlignment(QtCore.Qt.AlignTop)
        self.scrollContainer.setLayout(self.visibilityLayout)
        self.scrollArea.setWidget(self.scrollContainer)
        controlsLayout.addWidget(self.scrollArea, 1)

        self.splitter.addWidget(viewerWidget)
        self.splitter.addWidget(self.controlsWidget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([900, 320])

    def _connectSignals(self):
        self.saveButton.clicked.connect(self.gl_widget.save_screenshot)
        self.controlsButton.clicked.connect(self.gl_widget.toggle_help_overlay)

        self.modeCombo.currentIndexChanged.connect(self._onColorModeChange)

        self.isoButton.clicked.connect(self.gl_widget.set_isometric_view)
        self.xPosButton.clicked.connect(lambda: self.gl_widget.set_axis_view("x", negative=False))
        self.xNegButton.clicked.connect(lambda: self.gl_widget.set_axis_view("x", negative=True))
        self.yPosButton.clicked.connect(lambda: self.gl_widget.set_axis_view("y", negative=False))
        self.yNegButton.clicked.connect(lambda: self.gl_widget.set_axis_view("y", negative=True))
        self.zPosButton.clicked.connect(lambda: self.gl_widget.set_axis_view("z", negative=False))
        self.zNegButton.clicked.connect(lambda: self.gl_widget.set_axis_view("z", negative=True))

        self.rotateSlider.valueChanged.connect(self._updateCameraSpeeds)
        self.panSlider.valueChanged.connect(self._updateCameraSpeeds)
        self.zoomSlider.valueChanged.connect(self._updateCameraSpeeds)

        self.lightFollowCheckbox.toggled.connect(self._onLightFollowToggle)
        self.lightControlCheckbox.toggled.connect(self._onLightControlToggle)
        self.diffuseSlider.valueChanged.connect(self._onDiffuseChange)

    def _initializeState(self):
        if self.plotter.available:
            self.plotter.set_diffuse_fraction(0.1)
            self._populateVisibilityList(self.plotter.material_list())
        else:
            self.visibilityLayout.addWidget(QLabel("OpenMC not available.", self.scrollContainer))

        self._updateCameraSpeeds()

    def _makeScaledSlider(self, parent_layout, label_text, min_value, max_value, default_value):
        layout = QHBoxLayout()
        label = QLabel(label_text, self.controlsWidget)
        slider = QSlider(QtCore.Qt.Horizontal, self.controlsWidget)
        slider.setRange(0, 100)
        slider.setValue(self._sliderFromScale(default_value, min_value, max_value))
        value_label = QLabel(self.controlsWidget)

        def _updateValue(value):
            scaled = self._scaleFromSlider(value, min_value, max_value)
            value_label.setText(f"{scaled:.3f}")

        slider.valueChanged.connect(_updateValue)
        _updateValue(slider.value())

        layout.addWidget(label)
        layout.addWidget(slider, 1)
        layout.addWidget(value_label)
        parent_layout.addLayout(layout)
        return slider

    def _sliderFromScale(self, value, min_value, max_value):
        if max_value <= min_value:
            return 0
        return int(round((value - min_value) / (max_value - min_value) * 100))

    def _scaleFromSlider(self, value, min_value, max_value):
        return min_value + (max_value - min_value) * (value / 100.0)

    def _clearLayout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _populateVisibilityList(self, items):
        self._clearLayout(self.visibilityLayout)

        for domain_id, name in items:
            row = QWidget(self.scrollContainer)
            rowLayout = QHBoxLayout(row)
            rowLayout.setContentsMargins(0, 0, 0, 0)

            color_button = QPushButton(row)
            color_button.setFixedSize(20, 20)
            color = self.plotter.get_color(domain_id)
            self._setColorButtonStyle(color_button, color)

            label_text = f"{domain_id}"
            if name:
                label_text = f"{domain_id} - {name}"
            label = QLabel(label_text, row)
            label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

            checkbox = QCheckBox(row)
            checkbox.setChecked(True)

            checkbox.toggled.connect(
                lambda checked, did=domain_id: self._onVisibilityToggle(did, checked)
            )
            color_button.clicked.connect(
                lambda _=False, did=domain_id, button=color_button: self._onColorPick(did, button)
            )

            rowLayout.addWidget(color_button)
            rowLayout.addWidget(label, 1)
            rowLayout.addWidget(checkbox)
            self.visibilityLayout.addWidget(row)

    def _setColorButtonStyle(self, button, rgb):
        r, g, b = rgb
        button.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); border: 1px solid #555;"
        )

    def _onVisibilityToggle(self, domain_id, checked):
        self.plotter.set_visibility(domain_id, checked)
        self.gl_widget.request_final_render()

    def _onColorPick(self, domain_id, button):
        current = self.plotter.get_color(domain_id)
        initial = QtGui.QColor(*current)
        color = QColorDialog.getColor(initial, button, "Select Color")
        if not color.isValid():
            return
        rgb = (color.red(), color.green(), color.blue())
        self.plotter.set_color(domain_id, rgb)
        self._setColorButtonStyle(button, rgb)
        self.gl_widget.request_final_render()

    def _onColorModeChange(self, index):
        mode = self.modeCombo.itemData(index)
        self.plotter.set_color_by(mode)
        if mode == self.plotter.COLOR_BY_CELL:
            items = self.plotter.cell_list()
        else:
            items = self.plotter.material_list()
        self._populateVisibilityList(items)
        self.gl_widget.request_final_render()

    def _updateCameraSpeeds(self):
        rotate = self._scaleFromSlider(self.rotateSlider.value(), 0.001, 0.02)
        pan = self._scaleFromSlider(self.panSlider.value(), 0.2, 5.0)
        zoom = self._scaleFromSlider(self.zoomSlider.value(), 0.02, 0.5)
        self.gl_widget.set_camera_speeds(rotate=rotate, pan=pan, zoom=zoom)

    def _onLightFollowToggle(self, checked):
        if checked and self.lightControlCheckbox.isChecked():
            self.lightControlCheckbox.blockSignals(True)
            self.lightControlCheckbox.setChecked(False)
            self.lightControlCheckbox.blockSignals(False)
            self.gl_widget.set_light_control_mode(False)
        self.gl_widget.set_light_follows_camera(checked)

    def _onLightControlToggle(self, checked):
        if checked and self.lightFollowCheckbox.isChecked():
            self.lightFollowCheckbox.blockSignals(True)
            self.lightFollowCheckbox.setChecked(False)
            self.lightFollowCheckbox.blockSignals(False)
            self.gl_widget.set_light_follows_camera(False)
        self.gl_widget.set_light_control_mode(checked)

    def _onDiffuseChange(self, value):
        diffuse = value / 100.0
        self.diffuseValueLabel.setText(f"{diffuse:.2f}")
        self.plotter.set_diffuse_fraction(diffuse)
        self.gl_widget.request_final_render()
