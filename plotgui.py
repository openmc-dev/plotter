#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, openmc
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QApplication, QGroupBox, QFormLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QSizePolicy, QSpacerItem, QMainWindow,
    QCheckBox, QScrollArea, QLayout, QRubberBand, QMenu, QAction, QMenuBar,
    QFileDialog, QDialog, QTabWidget, QGridLayout, QToolButton, QColorDialog,
    QDialogButtonBox)
from plotmodel import PlotModel

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        # Set Window Title
        self.setWindowTitle('OpenMC Plot Explorer')

        # Create model
        self.model = PlotModel()

        # Create plot image
        self.plotIm = PlotImage(self.model)

        # Create menubar
        self.createMenuBar()

        # Create layout:
        self.createLayout()

        # Initiate color dialog object name
        self.colorDialog = None

        # Create, set main widget
        mainWidget = QWidget()
        mainWidget.setLayout(self.mainLayout)
        self.setCentralWidget(mainWidget)

        # Load Plot
        self.model.generatePlot()
        self.showCurrentPlot()
        self.updateControls(self.model.currentPlot)

        self.showStatusPlot()

    def undo(self):

        self.model.undo()
        self.showCurrentPlot()
        self.updateControls(self.model.activePlot)

        if not self.model.previousPlots:
            self.undoAction.setDisabled(True)

        self.redoAction.setDisabled(False)

    def redo(self):

        self.model.redo()
        self.showCurrentPlot()
        self.updateControls(self.model.activePlot)

        if not self.model.subsequentPlots:
            self.redoAction.setDisabled(True)

        self.undoAction.setDisabled(False)

    def showCurrentPlot(self):

        self.plotIm.scale = self.plotIm.updateScale()
        self.updateRelativeBases()

        # Update plot image
        self.pixmap = QtGui.QPixmap('plot.ppm')
        self.plotIm.setPixmap(self.pixmap)
        self.plotIm.adjustSize()

        self.adjustWindow()

        if self.model.previousPlots:
            self.undoAction.setDisabled(False)

        if self.model.subsequentPlots:
            self.redoAction.setDisabled(False)
        else:
            self.redoAction.setDisabled(True)

    def updateRelativeBases(self):
        # Determine image axes relative to plot
        if self.model.currentPlot['basis'][0] == 'x':
            basisX = ('xOr', self.xOr)
        else:
            basisX = ('yOr', self.yOr)
        if self.model.currentPlot['basis'][1] == 'y':
            basisY = ('yOr', self.yOr)
        else:
            basisY = ('zOr', self.zOr)
        self.plotIm.basisX = basisX
        self.plotIm.basisY = basisY

    def updateControls(self, plot, include_options=True):

        # Show plot values in GUI controls
        self.xOr.setText(str(plot['xOr']))
        self.yOr.setText(str(plot['yOr']))
        self.zOr.setText(str(plot['zOr']))
        self.width.setValue(plot['width'])
        self.height.setValue(plot['height'])
        if include_options:
            self.colorby.setCurrentText(plot['colorby'])
            self.basis.setCurrentText(plot['basis'])
            self.hRes.setValue(plot['hRes'])
            self.vRes.setValue(plot['vRes'])

    def createMenuBar(self):

        # Actions
        self.saveAction = QAction("&Save Image As...", self)
        self.saveAction.setShortcut(QtGui.QKeySequence.Save)
        self.saveAction.triggered.connect(self.saveImage)

        self.quitAction = QAction("&Quit", self)
        self.quitAction.setShortcut(QtGui.QKeySequence.Quit)
        self.quitAction.triggered.connect(self.close)

        self.applyAction = QAction("&Apply Changes", self)
        self.applyAction.setShortcut("Shift+Return")
        self.applyAction.triggered.connect(self.applyChanges)

        self.undoAction = QAction('&Undo', self)
        self.undoAction.setShortcut(QtGui.QKeySequence.Undo)
        self.undoAction.setDisabled(True)
        self.undoAction.triggered.connect(self.undo)

        self.redoAction = QAction('&Redo', self)
        self.redoAction.setDisabled(True)
        self.redoAction.setShortcut(QtGui.QKeySequence.Redo)
        self.redoAction.triggered.connect(self.redo)

        # Menus
        self.mainMenu = self.menuBar()
        #self.mainMenu.setNativeMenuBar(False)
        self.fileMenu = self.mainMenu.addMenu('&File')
        self.fileMenu.addAction(self.saveAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.quitAction)

        self.editMenu = self.mainMenu.addMenu('&Edit')
        self.editMenu.addAction(self.applyAction)
        self.editMenu.addSeparator()
        self.editMenu.addAction(self.undoAction)
        self.editMenu.addAction(self.redoAction)

    def createLayout(self):

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
        self.submitButton.clicked.connect(self.applyChanges)

        # Create control Layout
        self.controlLayout = QVBoxLayout()
        self.controlLayout.addWidget(self.originGroupBox)
        self.controlLayout.addWidget(self.optionsGroupBox)
        self.controlLayout.addWidget(self.resGroupBox)
        self.controlLayout.addWidget(self.submitButton)
        self.controlLayout.addStretch()

        # Create main Layout
        self.mainLayout = QHBoxLayout()
        self.mainLayout.addWidget(self.frame, 1)
        self.mainLayout.addLayout(self.controlLayout, 0)
        self.setLayout(self.mainLayout)

    def createOriginBox(self):

        cp = self.model.currentPlot

        # X Origin
        self.xOr = QLineEdit()
        self.xOr.setValidator(QtGui.QDoubleValidator())
        self.xOr.setText(str(cp['xOr']))
        self.xOr.setPlaceholderText('0.00')

        # Y Origin
        self.yOr = QLineEdit()
        self.yOr.setValidator(QtGui.QDoubleValidator())
        self.yOr.setText(str(cp['yOr']))
        self.yOr.setPlaceholderText('0.00')


        # Z Origin
        self.zOr = QLineEdit()
        self.zOr.setValidator(QtGui.QDoubleValidator())
        self.zOr.setText(str(cp['zOr']))
        self.zOr.setPlaceholderText('0.00')


        # Origin Form Layout
        self.orLayout = QFormLayout()
        self.orLayout.addRow('X:', self.xOr)
        self.orLayout.addRow('Y:', self.yOr)
        self.orLayout.addRow('Z:', self.zOr)
        self.orLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Origin Group Box
        self.originGroupBox = QGroupBox('ORIGIN')
        self.originGroupBox.setLayout(self.orLayout)

    def createOptionsBox(self):

        cp = self.model.currentPlot

        # Width
        self.width = QDoubleSpinBox(self)
        self.width.setRange(.1, 10000000)
        self.width.setValue(cp['width'])
        self.width.valueChanged.connect(self.onRatioChange)

        # Height
        self.height = QDoubleSpinBox(self)
        self.height.setRange(.1, 10000000)
        self.height.setValue(cp['height'])
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

        # Advanced Color Options
        self.colorOptionsButton = QPushButton('Color Options...')
        #self.colorOptionsButton.clicked.connect(self.loadColorOptions)

        # Options Form Layout
        self.opLayout = QFormLayout()
        self.opLayout.addRow('Width:', self.width)
        self.opLayout.addRow('Height', self.height)
        self.opLayout.addRow('Basis', self.basis)
        self.opLayout.addRow('Color By:', self.colorby)
        self.opLayout.addRow(self.colorOptionsButton)
        self.opLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Options Group Box
        self.optionsGroupBox = QGroupBox('OPTIONS')
        self.optionsGroupBox.setLayout(self.opLayout)

    def createResolutionBox(self):

        # Horizontal Resolution
        self.hRes = QSpinBox(self)
        self.hRes.setRange(1, 10000000)
        self.hRes.setValue(500)
        self.hRes.setSingleStep(25)
        self.hRes.valueChanged.connect(self.onRatioChange)

        # Vertical Resolution
        self.vResLabel = QLabel('Pixel Height')
        self.vResLabel.setDisabled(True)
        self.vRes = QSpinBox(self)
        self.vRes.setRange(1, 10000000)
        self.vRes.setValue(500)
        self.vRes.setSingleStep(25)
        self.vRes.setDisabled(True)

        # Ratio checkbox
        self.ratioCheck = QCheckBox("Fixed Aspect Ratio", self)
        self.ratioCheck.toggle()
        self.ratioCheck.stateChanged.connect(self.onAspectLockChange)

        # Resolution Form Layout
        self.resLayout = QFormLayout()
        self.resLayout.addRow(self.ratioCheck)
        self.resLayout.addRow('Pixel Width:', self.hRes)
        self.resLayout.addRow(self.vResLabel, self.vRes)
        self.resLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Resolution Group Box
        self.resGroupBox = QGroupBox("RESOLUTION")
        self.resGroupBox.setLayout(self.resLayout)

    def applyChanges(self):

        # Convert origin values to float
        for value in [self.xOr, self.yOr, self.zOr]:
            try:
                value.setText(str(float(value.text().replace(",", ""))))
            except ValueError:
                value.setText('0.0')

        # Update active plot
        self.model.activePlot['xOr'] = float(self.xOr.text())
        self.model.activePlot['yOr'] = float(self.yOr.text())
        self.model.activePlot['zOr'] = float(self.zOr.text())
        self.model.activePlot['colorby'] = self.colorby.currentText()
        self.model.activePlot['basis'] = self.basis.currentText()
        self.model.activePlot['width'] = self.width.value()
        self.model.activePlot['height'] = self.height.value()
        self.model.activePlot['hRes'] = self.hRes.value()
        self.model.activePlot['vRes'] = self.vRes.value()

        # Check that active plot is different from current plot
        if self.model.activePlot != self.model.currentPlot:
            self.model.storeCurrent()
            # Clear subsequentPlots
            self.model.subsequentPlots = []

            # Update plot.xml and display image
            self.model.generatePlot()
            self.showCurrentPlot()

    def onAspectLockChange(self, state):
        if state == QtCore.Qt.Checked:
            self.onRatioChange()
            self.vRes.setDisabled(True)
            self.vResLabel.setDisabled(True)
        else:
            self.vRes.setDisabled(False)
            self.vResLabel.setDisabled(False)

    def onRatioChange(self):
        if self.ratioCheck.isChecked():
            ratio = self.width.value() / self.height.value()
            self.vRes.setValue(int(self.hRes.value() / ratio))

    def saveImage(self):
        filename, ext = QFileDialog.getSaveFileName(self, "Save Plot Image",
                                            "untitled", "Images (*.png *.ppm)")
        if filename:
            if "." not in filename:
                self.pixmap.save(filename + ".png")
            else:
                self.pixmap.save(filename)

    def showStatusPlot(self):
        cp = self.model.currentPlot
        message = (f"Origin: ({cp['xOr']}, {cp['yOr']}, {cp['zOr']})  |  "
            f"Width: {cp['width']} Height: {cp['height']}  |  "
            f"Color By: {cp['colorby']}  |  Basis: {cp['basis']}")
        self.statusBar().showMessage(message)

    def adjustWindow(self):
        # Get screen dimensions
        self.screen = app.desktop().screenGeometry()
        self.setMaximumSize(self.screen.width(), self.screen.height())

        # Adjust scroll area to fit plot if window will not exeed screen size
        if self.hRes.value() < .8 * self.screen.width():
            self.frame.setMinimumWidth(self.plotIm.width() + 20)
        else:
            self.frame.setMinimumWidth(20)
        if self.vRes.value() < .85 * self.screen.height():
            self.frame.setMinimumHeight(self.plotIm.height() + 20)
        else:
            self.frame.setMinimumHeight(20)

class PlotImage(QLabel):
    def __init__(self, model):
        super(PlotImage, self).__init__()

        self.model = model

        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMouseTracking(True)

        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        self.bandOrigin = QtCore.QPoint()
        self.xBandOrigin = None
        self.yBandOrigin = None

        self.scale = self.updateScale()
        self.basisX, self.basisY = (None, None)
 
    def updateScale(self):
        # Determine Scale of image / plot
        scale = (self.model.currentPlot['hRes'] /
                 self.model.currentPlot['width'],
                 self.model.currentPlot['vRes'] /
                 self.model.currentPlot['height'])
        return scale

    def enterEvent(self, event):
        self.setCursor(QtCore.Qt.CrossCursor)

    def leaveEvent(self, event):
        mainWindow.showStatusPlot()

    def mousePressEvent(self, event):

        cp = self.model.currentPlot

        # Cursor position in pixels relative to center of plot image
        xPos = event.pos().x() - (cp['hRes'] / 2)
        yPos = -event.pos().y() + (cp['vRes'] / 2)

        # Curson position in plot units relative to model
        self.xBandOrigin = (xPos / self.scale[0]) + cp[self.basisX[0]]
        self.yBandOrigin = (yPos / self.scale[1]) + cp[self.basisY[0]]

        # Create rubber band
        self.rubberBand.setGeometry(QtCore.QRect(self.bandOrigin, QtCore.QSize()))

        # Rubber band start position
        self.bandOrigin = event.pos()

        QLabel.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):

        cp = self.model.currentPlot

        # Cursor position in pixels relative to center of image
        xPos = event.pos().x() - (cp['hRes'] / 2) #+ 1
        yPos = (-event.pos().y() + (cp['vRes'] / 2)) #+ 1

        # Cursor position in plot units relative to model
        xPlotPos = (xPos / self.scale[0]) + cp[self.basisX[0]]
        yPlotPos = (yPos / self.scale[1]) + cp[self.basisY[0]]

        # Show Cursor position relative to plot in status bar
        if self.model.currentPlot['basis'] == 'xy':
            mainWindow.statusBar().showMessage(f"Plot Position: "
                f"({round(xPlotPos, 2)}, {round(yPlotPos, 2)}, {round(cp['zOr'], 2)})")
        elif self.model.currentPlot['basis'] == 'xz':
            mainWindow.statusBar().showMessage(f"Plot Position: "
                f"({round(xPlotPos, 2)}, {round(cp['yOr'], 2)}, {round(yPlotPos, 2)})")
        else:
            mainWindow.statusBar().showMessage(f"Plot Position: "
                f"({round(cp['xOr'], 2)}, {round(xPlotPos, 2)}, {round(yPlotPos, 2)})")

        # Update rubber band and values if mouse button held down
        if app.mouseButtons() in [QtCore.Qt.LeftButton, QtCore.Qt.RightButton]:
            self.rubberBand.setGeometry(
                QtCore.QRect(self.bandOrigin, event.pos()).normalized())

            # Show rubber band if both dimensions > 10 pixels
            if self.rubberBand.width() > 10 and self.rubberBand.height() > 10:
                self.rubberBand.show()
            else:
                self.rubberBand.hide()

            # Update plot X Origin
            xcenter = (self.xBandOrigin + xPlotPos) / 2
            self.basisX[1].setText(str(round(xcenter, 9)))

            # Update plot Y Origin
            ycenter = (self.yBandOrigin + yPlotPos) / 2
            self.basisY[1].setText(str(round(ycenter, 9)))

        # Zoom in to rubber band rectangle if left button held
        if app.mouseButtons() == QtCore.Qt.LeftButton:

            # Update width and height
            mainWindow.width.setValue(abs(self.xBandOrigin - xPlotPos))
            mainWindow.height.setValue(abs(self.yBandOrigin - yPlotPos))

        # Zoom out if right button held. Larger rectangle = more zoomed out
        elif app.mouseButtons() == QtCore.Qt.RightButton:

            # Update width
            bandwidth = abs(self.bandOrigin.x() - event.pos().x())
            width = cp['width'] * (cp['hRes'] / max(bandwidth, .001))
            mainWindow.width.setValue(width)

            # Update height
            bandheight = abs(self.bandOrigin.y() - event.pos().y())
            height = cp['height'] * (cp['vRes'] / max(bandheight, .001))
            mainWindow.height.setValue(height)

    def mouseReleaseEvent(self, event):
        if self.rubberBand.isVisible():
            self.rubberBand.hide()
            mainWindow.applyChanges()
        else:
            mainWindow.updateControls(self.model.currentPlot, False)


if __name__ == '__main__':

    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
