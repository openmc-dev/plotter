#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, openmc
from PySide2.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QApplication, QGroupBox, QFormLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QSizePolicy, QSpacerItem, QMainWindow,
    QCheckBox, QScrollArea, QStyleFactory, QLayout)
from PySide2 import QtCore, QtGui


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        # Set max window size to fit screen
        self.screen = app.desktop().screenGeometry()
        self.setMaximumSize(self.screen.width(), self.screen.height())

        # Create, set main widget
        self.mainwid = MainWidget()
        self.setCentralWidget(self.mainwid)

        self.setWindowTitle('OpenMC Plot Explorer')

        # Create status bar
        #self.updateStatus()

        # Load Plot
        self.mainwid.onSubmit()


    def updateStatus(self):
        mw = self.mainwid
        self.statusBar().showMessage(f'Origin: ({float(mw.xOrigin.text())}, '
            f'{float(mw.yOrigin.text())}, {mw.zOrigin.text()})  |  Width: '
            f'{mw.width.value()} Height: {mw.height.value()}  |  Color By: '
            f'{mw.colorby.currentText()}  |  Basis: {mw.basis.currentText()}')


class MainWidget(QWidget):
    def __init__(self):
        super(MainWidget, self).__init__()

        # Plot
        self.plot = QLabel()
        self.plot.setAlignment(QtCore.Qt.AlignCenter)
        #self.plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot.setMargin(0)
        self.plot.setStyleSheet('margin: 0; padding: 0')

        # Scroll Area
        self.frame = QScrollArea(self)
        self.frame.setAlignment(QtCore.Qt.AlignCenter)
        self.frame.setWidget(self.plot)
        self.frame.setContentsMargins(0,0,0,0)
        #self.frame.setSizeAdjustPolicy(QScrollArea.AdjustToContents)
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.frame.setStyleSheet('margin: 0; padding: 0')

        # Create Controls
        self.createOriginBox()
        self.createOptionsBox()
        self.createResolutionBox()

        # Submit button
        self.submitButton = QPushButton("Submit", self)
        self.submitButton.clicked.connect(self.onSubmit)

        # Control Layout
        self.controlLayout = QVBoxLayout()
        self.controlLayout.addWidget(self.originGroupBox)
        self.controlLayout.addWidget(self.optionsGroupBox)
        self.controlLayout.addWidget(self.pixelGroupBox)
        self.controlLayout.addWidget(self.submitButton)
        self.controlLayout.addStretch()

        # Main Layout
        self.mainLayout = QHBoxLayout()
        self.mainLayout.addWidget(self.frame, 1)
        self.mainLayout.addLayout(self.controlLayout, 0)
        self.setLayout(self.mainLayout)


    def onSubmit(self):

        for value in [self.xOrigin, self.yOrigin, self.zOrigin]:
            try:
                value.setText(str(float(value.text().replace(",", ""))))
            except:
                value.setText('0.0')

        # Generate plot.xml
        plot = openmc.Plot()
        plot.filename = 'plot'
        plot.color_by = self.colorby.currentText()
        plot.basis = self.basis.currentText()
        plot.origin = (float(self.xOrigin.text()), float(self.yOrigin.text()),
                       float(self.zOrigin.text()))
        plot.width = (self.width.value(), self.height.value())
        plot.background = 'black'
        plot.pixels = (self.pixelWidth.value(), self.pixelHeight.value())

        plots = openmc.Plots([plot])
        plots.export_to_xml()
        openmc.plot_geometry()

        # Update Pixmap
        self.plot.setPixmap(QtGui.QPixmap('plot.ppm'))
        self.plot.adjustSize()


        # Get screen dimensions
        self.screen = app.desktop().screenGeometry()


        # Adjust main window size:
        # Adjust scroll area to fit plot if window will not exeed screen size
        # TODO figure out how to clean this up / do this correctly?
        if self.pixelWidth.value() < .8 * self.screen.width():
            self.frame.setMinimumWidth(self.plot.width() + 20)
        else:
            self.frame.setMinimumWidth(20)
        if self.pixelHeight.value() < .85 * self.screen.height():
            self.frame.setMinimumHeight(self.plot.height() + 20)
        else:
            self.frame.setMinimumHeight(20)

        # Update status bar
        self.parentWidget().updateStatus()


    def onAspectLockChange(self,state):
        if state == QtCore.Qt.Checked:
            ratio = self.width.value() / self.height.value()
            self.pixelHeight.setValue(int(self.pixelWidth.value() / ratio))
            self.pixelHeight.setDisabled(True)
            self.pixelHeightLabel.setDisabled(True)
        else:
            self.pixelHeight.setDisabled(False)
            self.pixelHeightLabel.setDisabled(False)


    def onRatioChange(self, value):
        if self.ratioCheck.isChecked():
            ratio = self.width.value() / self.height.value()
            self.pixelHeight.setValue(int(self.pixelWidth.value() / ratio))


    def createOriginBox(self):

        # X Origin
        self.xOrigin = QLineEdit()
        self.xOrigin.setValidator(QtGui.QDoubleValidator())
        self.xOrigin.setText('0.00')
        self.xOrigin.setPlaceholderText('0.00')

        # Y Origin
        self.yOrigin = QLineEdit()
        self.yOrigin.setValidator(QtGui.QDoubleValidator())
        self.yOrigin.setText('0.00')
        self.yOrigin.setPlaceholderText('0.00')

        # Z Origin
        self.zOrigin = QLineEdit()
        self.zOrigin.setValidator(QtGui.QDoubleValidator())
        self.zOrigin.setText('0.00')
        self.zOrigin.setPlaceholderText('0.00')

        # Origin Form Layout
        self.originLayout = QFormLayout()
        self.originLayout.addRow('X:', self.xOrigin)
        self.originLayout.addRow('Y:', self.yOrigin)
        self.originLayout.addRow('Z:', self.zOrigin)
        self.originLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Origin Group Box
        self.originGroupBox = QGroupBox('ORIGIN')
        self.originGroupBox.setLayout(self.originLayout)


    def createOptionsBox(self):

        # Width
        self.width = QDoubleSpinBox(self)
        self.width.setValue(25)
        self.width.setRange(1, 10000000)
        self.width.valueChanged.connect(self.onRatioChange)

        # Height
        self.height = QDoubleSpinBox(self)
        self.height.setValue(25)
        self.height.setRange(1, 10000000)
        self.height.valueChanged.connect(self.onRatioChange)

        # ColorBy
        self.colorby = QComboBox(self)
        self.colorby.addItem("material")
        self.colorby.addItem("cell")

        # Basis
        self.basis = QComboBox(self)
        self.basis.addItem("xy")
        self.basis.addItem("xz")
        self.basis.addItem("yz")

        # Options Form Layout
        self.optionsLayout = QFormLayout()
        self.optionsLayout.addRow('Width:', self.width)
        self.optionsLayout.addRow('Height', self.height)
        self.optionsLayout.addRow('Color By:', self.colorby)
        self.optionsLayout.addRow('Basis', self.basis)
        self.optionsLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Options Group Box
        self.optionsGroupBox = QGroupBox('OPTIONS')
        self.optionsGroupBox.setLayout(self.optionsLayout)


    def createResolutionBox(self):

        # Horizontal Resolution
        self.pixelWidth = QSpinBox(self)
        self.pixelWidth.setRange(1, 10000000)
        self.pixelWidth.setValue(500)
        self.pixelWidth.valueChanged.connect(self.onRatioChange)
        self.pixelWidth.setSingleStep(5)

        # Vertical Resolution
        self.pixelHeightLabel = QLabel('Pixel Height')
        self.pixelHeightLabel.setDisabled(True)
        self.pixelHeight = QSpinBox(self)
        self.pixelHeight.setRange(1, 10000000)
        self.pixelHeight.setValue(500)
        self.pixelHeight.setSingleStep(5)
        self.pixelHeight.setDisabled(True)

        # Ratio checkbox
        self.ratioCheck = QCheckBox("Fixed Aspect Ratio", self)
        self.ratioCheck.toggle()
        self.ratioCheck.stateChanged.connect(self.onAspectLockChange)

        # Pixel Form Layout
        self.pixelLayout = QFormLayout()
        self.pixelLayout.addRow(self.ratioCheck)
        self.pixelLayout.addRow('Pixel Width:', self.pixelWidth)
        self.pixelLayout.addRow(self.pixelHeightLabel, self.pixelHeight)
        self.pixelLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Pixel Group Box
        self.pixelGroupBox = QGroupBox("PIXELS")
        self.pixelGroupBox.setLayout(self.pixelLayout)


if __name__ == '__main__':

    app = QApplication(sys.argv)
    mainw = MainWindow()
    mainw.show()
    sys.exit(app.exec_())
