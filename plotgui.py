#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, openmc
from collections import defaultdict
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QApplication, QGroupBox, QFormLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QSizePolicy, QSpacerItem, QMainWindow,
    QCheckBox, QScrollArea, QLayout, QRubberBand)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        # Set max window size to fit screen
        self.screen = app.desktop().screenGeometry()
        self.setMaximumSize(self.screen.width(), self.screen.height())

        # Create, set main widget
        self.mainWidget = MainWidget()
        self.setCentralWidget(self.mainWidget)

        # Set Window Title
        self.setWindowTitle('OpenMC Plot Explorer')

        # Load Plot
        self.mainWidget.updatePlot()


    def updateStatus(self):
        cp = self.mainWidget.plotIm.currentPlot
        self.statusBar().showMessage(f"Origin: ({cp['xOr']}, {cp['yOr']}, "
            f"{cp['zOr']})  |  Width: {cp['width']} Height: {cp['height']}  |  "
            f"Color By: {cp['cb']}  |  Basis: {cp['basis']}")


class MainWidget(QWidget):
    def __init__(self):
        super(MainWidget, self).__init__()

        # Plot
        self.plotIm = PlotImage()
        self.plotIm.setAlignment(QtCore.Qt.AlignCenter)

        # Scroll Area
        self.frame = QScrollArea(self)
        self.frame.setAlignment(QtCore.Qt.AlignCenter)
        self.frame.setWidget(self.plotIm)
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Create Controls
        self.createOriginBox()
        self.createOptionsBox()
        self.createResolutionBox()

        # Create submit button
        self.submitButton = QPushButton("Apply Changes", self)
        self.submitButton.clicked.connect(self.updatePlot)

        # Create control Layout
        self.controlLayout = QVBoxLayout()
        self.controlLayout.addWidget(self.originGroupBox)
        self.controlLayout.addWidget(self.optionsGroupBox)
        self.controlLayout.addWidget(self.pixelGroupBox)
        self.controlLayout.addWidget(self.submitButton)
        self.controlLayout.addStretch()

        # Create main Layout
        self.mainLayout = QHBoxLayout()
        self.mainLayout.addWidget(self.frame, 1)
        self.mainLayout.addLayout(self.controlLayout, 0)
        self.setLayout(self.mainLayout)


    def updatePlot(self):

        # Hide rubber band rectangle
        self.plotIm.rubberBand.hide()

        self.saveCurrentPlot()
        self.generatePlot()

        # Update Pixmap
        self.plotIm.setPixmap(QtGui.QPixmap('plot.ppm'))
        self.plotIm.adjustSize()

        # Get screen dimensions
        self.screen = app.desktop().screenGeometry()

        # Adjust scroll area to fit plot if window will not exeed screen size
        if self.pixelWidth.value() < .8 * self.screen.width():
            self.frame.setMinimumWidth(self.plotIm.width() + 20)
        else:
            self.frame.setMinimumWidth(20)
        if self.pixelHeight.value() < .85 * self.screen.height():
            self.frame.setMinimumHeight(self.plotIm.height() + 20)
        else:
            self.frame.setMinimumHeight(20)

        # Update status bar
        self.parentWidget().updateStatus()

        # Determine Scale of image / plot
        self.plotIm.scale = (self.pixelWidth.value() / self.width.value(),
                           self.pixelHeight.value() / self.height.value())

        # Determine image axis relative to plot
        if self.basis.currentText()[0] == 'x':
            self.plotIm.imageX = ('xOr', self.plotIm.xOrigin)
        else:
            self.plotIm.imageX = ('yOr', self.plotIm.yOrigin)

        if self.basis.currentText()[1] == 'y':
            self.plotIm.imageY = ('yOr', self.plotIm.yOrigin)
        else:
            self.plotIm.imageY = ('zOr', self.plotIm.zOrigin)


    def generatePlot(self):

        cp = self.plotIm.currentPlot

        # Generate plot.xml
        plot = openmc.Plot()
        plot.filename = 'plot'
        plot.color_by = cp['cb']
        plot.basis = cp['basis']
        plot.origin = (cp['xOr'], cp['yOr'], cp['zOr'])
        plot.width = (cp['width'], cp['height'])
        plot.background = 'black'
        plot.pixels = (cp['pixwidth'], cp['pixheight'])

        plots = openmc.Plots([plot])
        plots.export_to_xml()
        openmc.plot_geometry()


    def saveCurrentPlot(self):

        # Convert origin values to float
        for value in [self.plotIm.xOrigin, self.plotIm.yOrigin, self.plotIm.zOrigin]:
            try:
                value.setText(str(float(value.text().replace(",", ""))))
            except:
                value.setText('0.0')

        # Create dict of current plot values
        self.plotIm.currentPlot['xOr'] = float(self.plotIm.xOrigin.text())
        self.plotIm.currentPlot['yOr'] = float(self.plotIm.yOrigin.text())
        self.plotIm.currentPlot['zOr'] = float(self.plotIm.zOrigin.text())
        self.plotIm.currentPlot['cb'] = self.colorby.currentText()
        self.plotIm.currentPlot['basis'] = self.basis.currentText()
        self.plotIm.currentPlot['width'] = self.width.value()
        self.plotIm.currentPlot['height'] = self.height.value()
        self.plotIm.currentPlot['pixwidth'] = self.pixelWidth.value()
        self.plotIm.currentPlot['pixheight'] = self.pixelHeight.value()

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
        self.plotIm.xOrigin = QLineEdit()
        self.plotIm.xOrigin.setValidator(QtGui.QDoubleValidator())
        self.plotIm.xOrigin.setText('0.00')
        self.plotIm.xOrigin.setPlaceholderText('0.00')

        # Y Origin
        self.plotIm.yOrigin = QLineEdit()
        self.plotIm.yOrigin.setValidator(QtGui.QDoubleValidator())
        self.plotIm.yOrigin.setText('0.00')
        self.plotIm.yOrigin.setPlaceholderText('0.00')

        # Z Origin
        self.plotIm.zOrigin = QLineEdit()
        self.plotIm.zOrigin.setValidator(QtGui.QDoubleValidator())
        self.plotIm.zOrigin.setText('0.00')
        self.plotIm.zOrigin.setPlaceholderText('0.00')

        # Origin Form Layout
        self.originLayout = QFormLayout()
        self.originLayout.addRow('X:', self.plotIm.xOrigin)
        self.originLayout.addRow('Y:', self.plotIm.yOrigin)
        self.originLayout.addRow('Z:', self.plotIm.zOrigin)
        self.originLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Origin Group Box
        self.originGroupBox = QGroupBox('ORIGIN')
        self.originGroupBox.setLayout(self.originLayout)


    def createOptionsBox(self):

        # Width
        self.width = QDoubleSpinBox(self)
        self.width.setValue(25)
        self.width.setRange(.1, 10000000)
        self.width.valueChanged.connect(self.onRatioChange)

        # Height
        self.height = QDoubleSpinBox(self)
        self.height.setValue(25)
        self.height.setRange(.1, 10000000)
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


class PlotImage(QLabel):
    def __init__(self):
        super(PlotImage, self).__init__()

        self.setMouseTracking(True)
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        self.previousPlots = []
        self.currentPlot = {}
        self.origin = QtCore.QPoint()
        self.scale = 1

    def mousePressEvent(self, event):

        cp = self.currentPlot

        # Restore fields to current values
        if self.rubberBand.isVisible():
            self.xOrigin.setText(str(cp['xOr']))
            self.yOrigin.setText(str(cp['yOr']))
            self.zOrigin.setText(str(cp['zOr']))
            mainWindow.mainWidget.width.setValue(cp['width'])
            mainWindow.mainWidget.height.setValue(cp['height'])

            self.rubberBand.hide()

        # Cursor position in pixels relative to center of image
        xPos = event.pos().x() - (cp['pixwidth'] / 2)
        yPos = -event.pos().y() + (cp['pixheight'] / 2)

        # Curson position relative to plot
        self.xBandOrigin = (xPos / self.scale[0]) + cp[self.imageX[0]]
        self.yBandOrigin = (yPos / self.scale[1]) + cp[self.imageY[0]]

        # Rubber band start position
        self.origin = event.pos()

        # Create rubber band
        self.rubberBand.setGeometry(QtCore.QRect(self.origin, QtCore.QSize()))

        QLabel.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):

        cp = self.currentPlot

        # Cursor position in pixels relative to center of image
        xPos = event.pos().x() - (cp['pixwidth'] / 2) #+ 1
        yPos = (-event.pos().y() + (cp['pixheight'] / 2)) #+ 1

        # Cursor position relative to plot
        xPlotPos = (xPos / self.scale[0]) + cp[self.imageX[0]]
        yPlotPos = (yPos / self.scale[1]) + cp[self.imageY[0]]

        # Show Cursor position relative to plot in status bar
        if mainWindow.mainWidget.basis.currentText() == 'xy':
            mainWindow.statusBar().showMessage(f"Plot Position: ({round(xPlotPos, 2)}, "
                                        f"{round(yPlotPos, 2)}, {cp['zOr']})")
        elif mainWindow.mainWidget.basis.currentText() == 'xz':
            mainWindow.statusBar().showMessage(f"Plot Position: ({round(xPlotPos, 2)}, "
                                        f"{cp['yOr']}, {round(yPlotPos, 2)})")
        else:
            mainWindow.statusBar().showMessage(f"Plot Position: ({cp['xOr']}, "
                                        f"{round(xPlotPos, 2)}, {round(yPlotPos, 2)})")

        # Update rubber band and values if mouse button held down
        if app.mouseButtons() in [QtCore.Qt.LeftButton, QtCore.Qt.RightButton]:
            self.rubberBand.setGeometry(
                QtCore.QRect(self.origin, event.pos()).normalized())

            if self.rubberBand.width() > 5 or self.rubberBand.height() > 5:
                self.rubberBand.show()

            # Update x Origin
            xcenter = self.xBandOrigin + ((xPlotPos - self.xBandOrigin) / 2)
            self.imageX[1].setText(str(round(xcenter, 9)))

            # Update y Origin
            ycenter = self.yBandOrigin + ((yPlotPos - self.yBandOrigin) / 2)
            self.imageY[1].setText(str(round(ycenter, 9)))

            # Zoom in to rubber band rectangle if left button held
            if app.mouseButtons() == QtCore.Qt.LeftButton:

                # Update width
                width = abs(self.xBandOrigin - xPlotPos)
                mainWindow.mainWidget.width.setValue(width)

                # Update height
                height = abs(self.yBandOrigin - yPlotPos)
                mainWindow.mainWidget.height.setValue(height)

            # Zoom out if right button held. Larger rectangle = more zoomed out
            elif app.mouseButtons() == QtCore.Qt.RightButton:

                # Update width
                width = cp['width'] * (1 + (abs(self.origin.x()
                                    - event.pos().x()) / cp['pixwidth']) * 4)
                mainWindow.mainWidget.width.setValue(width)

                # Update height
                height = cp['height'] * (1 + (abs(self.origin.y()
                                    - event.pos().y()) / cp['pixheight']) * 4)
                mainWindow.mainWidget.height.setValue(height)

    def enterEvent(self, event):
        self.setCursor(QtCore.Qt.CrossCursor)

    def leaveEvent(self, event):
        mainWindow.updateStatus()


if __name__ == '__main__':

    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
