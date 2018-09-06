#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, openmc
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QApplication, QGroupBox, QFormLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QSizePolicy, QSpacerItem, QMainWindow,
    QCheckBox, QScrollArea, QLayout, QRubberBand, QMenu, QAction, QMenuBar,
    QFileDialog, QDialog, QTabWidget, QGridLayout, QToolButton, QColorDialog,
    QDialogButtonBox, QFrame, QActionGroup, QDockWidget)
from plotmodel import PlotModel

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        # Set Window Title
        self.setWindowTitle('OpenMC Plot Explorer')
        self.move(100,100)

        # Create model
        self.model = PlotModel()

        # Create plot image
        self.plotIm = PlotImage(self.model)
        self.frame = QScrollArea(self)
        self.frame.setAlignment(QtCore.Qt.AlignCenter)
        self.frame.setWidget(self.plotIm)
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCentralWidget(self.frame)

        # Create Plot Options Dock
        self.optionsDock = QDockWidget('Options Dock', self)
        self.optionsDock.setObjectName('optionsDock')
        self.optionsDock.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.optionsDock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea |
                                    QtCore.Qt.RightDockWidgetArea)
        self.optionsWidget = QWidget()
        self.createDockLayout()
        self.optionsDock.setWidget(self.optionsWidget)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.optionsDock)

        # Initiate color dialog
        self.colorDialog = ColorDialog(self.model, self.applyChanges, self)
        self.colorDialog.move(600, 200)
        self.colorDialog.hide()

        # Create menubar
        self.createMenuBar()

        # Load Plot
        self.model.generatePlot()
        self.showCurrentPlot()
        self.updateControls(self.model.currentPlot)

        # Status Bar
        #self.statusBar().setSizeGripEnabled(False)
        self.coordLabel = QLabel()
        self.statusBar().addPermanentWidget(self.coordLabel)
        self.coordLabel.hide()

        self.showStatusPlot()

    def createMenuBar(self):

        # Menus
        self.mainMenu = self.menuBar()

        # File Menu
        self.fileMenu = self.mainMenu.addMenu('&File')

        self.saveAction = QAction("&Save Image As...", self)
        self.saveAction.setShortcut(QtGui.QKeySequence.Save)
        self.saveAction.triggered.connect(self.saveImage)

        self.quitAction = QAction("&Quit", self)
        self.quitAction.setShortcut(QtGui.QKeySequence.Quit)
        self.quitAction.triggered.connect(self.close)

        self.fileMenu.addAction(self.saveAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.quitAction)

        # Edit Menu
        self.editMenu = self.mainMenu.addMenu('&Edit')

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

        self.restoreAction = QAction("&Restore To Default", self)
        self.restoreAction.setShortcut("Ctrl+R")
        self.restoreAction.triggered.connect(self.restoreDefault)

        self.editMenu.addAction(self.applyAction)
        self.editMenu.addSeparator()
        self.editMenu.addAction(self.undoAction)
        self.editMenu.addAction(self.redoAction)
        self.editMenu.addAction(self.restoreAction)
        self.editMenu.addSeparator()

        # Edit -> Basis Menu
        self.xyAction = QAction('&xy  ', self)
        self.xyAction.setCheckable(True)
        self.xyAction.setShortcut('Alt+X')
        self.xyAction.triggered.connect(lambda : self.editBasis('xy'))

        self.xzAction = QAction('x&z  ', self)
        self.xzAction.setCheckable(True)
        self.xzAction.setShortcut('Alt+Z')
        self.xzAction.triggered.connect(lambda : self.editBasis('xz'))

        self.yzAction = QAction('&yz  ', self)
        self.yzAction.setCheckable(True)
        self.yzAction.setShortcut('Alt+Y')
        self.yzAction.triggered.connect(lambda : self.editBasis('yz'))

        self.basisMenu = self.editMenu.addMenu('&Basis')
        self.basisMenu.addAction(self.xyAction)
        self.basisMenu.addAction(self.xzAction)
        self.basisMenu.addAction(self.yzAction)
        self.basisMenu.aboutToShow.connect(self.updateBasisMenu)

        # Edit -> Color By Menu
        self.cellAction = QAction('&Cell', self)
        self.cellAction.setCheckable(True)
        self.cellAction.setShortcut('Alt+C')
        self.cellAction.triggered.connect(lambda : self.editColorBy('cell'))

        self.materialAction = QAction('&Material', self)
        self.materialAction.setCheckable(True)
        self.materialAction.setShortcut('Alt+M')
        self.materialAction.triggered.connect(lambda : self.editColorBy('material'))

        self.colorbyMenu = self.editMenu.addMenu('&Color By')
        self.colorbyMenu.addAction(self.cellAction)
        self.colorbyMenu.addAction(self.materialAction)
        self.colorbyMenu.aboutToShow.connect(self.updateColorbyMenu)

        # View Menu
        self.viewMenu = self.mainMenu.addMenu('&View')
        self.viewDockAction = QAction('Hide Options &Dock', self)
        self.viewDockAction.setShortcut("Ctrl+D")
        self.viewDockAction.triggered.connect(self.toggleDockView)
        self.viewMenu.addAction(self.viewDockAction)
        self.viewMenu.aboutToShow.connect(self.updateViewMenu)

        # Window Menu
        self.windowMenu = self.mainMenu.addMenu('&Window')
        self.mainWindowAction = QAction('&Main Window', self)
        self.mainWindowAction.setShortcut('Alt+W')
        self.mainWindowAction.setCheckable(True)
        self.mainWindowAction.triggered.connect(self.showMainWindow)
        self.colorDialogAction = QAction('Color &Dialog', self)
        self.colorDialogAction.setShortcut('Alt+D')
        self.colorDialogAction.setCheckable(True)
        self.colorDialogAction.triggered.connect(self.showColorDialog)
        self.windowMenu.addAction(self.mainWindowAction)
        self.windowMenu.addAction(self.colorDialogAction)
        self.windowMenu.aboutToShow.connect(self.updateWindowMenu)

    def updateBasisMenu(self):

        self.xyAction.setChecked(self.model.currentPlot['basis'] == 'xy')
        self.xzAction.setChecked(self.model.currentPlot['basis'] == 'xz')
        self.yzAction.setChecked(self.model.currentPlot['basis'] == 'yz')

    def updateColorbyMenu(self):

        self.cellAction.setChecked(self.model.currentPlot['colorby'] == 'cell')
        self.materialAction.setChecked(self.model.currentPlot['colorby'] == 'material')

    def updateViewMenu(self):

        if self.optionsDock.isVisible():
            self.viewDockAction.setText('Hide Options &Dock')
        else:
            self.viewDockAction.setText('Show Options &Dock')

    def updateWindowMenu(self):

        self.colorDialogAction.setChecked(self.colorDialog.isActiveWindow())
        self.mainWindowAction.setChecked(self.isActiveWindow())

    def showMainWindow(self):
        self.raise_()
        self.activateWindow()

    def toggleDockView(self):

        if self.optionsDock.isVisible():
            self.optionsDock.hide()
        else:
            self.optionsDock.setVisible(True)

        self.showMainWindow()

    def createDockLayout(self):

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

        self.optionsWidget.setLayout(self.controlLayout)

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
        self.originGroupBox = QGroupBox('Origin')
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
        self.colorby.currentTextChanged.connect(self.toggleColorBy)

        # Basis
        self.basis = QComboBox(self)
        self.basis.addItem("xy")
        self.basis.addItem("xz")
        self.basis.addItem("yz")

        # Advanced Color Options
        self.colorOptionsButton = QPushButton('Color Options...')
        self.colorOptionsButton.clicked.connect(self.showColorDialog)

        # Options Form Layout
        self.opLayout = QFormLayout()
        self.opLayout.addRow('Width:', self.width)
        self.opLayout.addRow('Height:', self.height)
        self.opLayout.addRow('Basis:', self.basis)
        self.opLayout.addRow('Color By:', self.colorby)
        self.opLayout.addRow(self.colorOptionsButton)
        self.opLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Options Group Box
        self.optionsGroupBox = QGroupBox('Options')
        self.optionsGroupBox.setLayout(self.opLayout)

    def createResolutionBox(self):

        # Horizontal Resolution
        self.hRes = QSpinBox(self)
        self.hRes.setRange(1, 10000000)
        self.hRes.setValue(500)
        self.hRes.setSingleStep(25)
        self.hRes.valueChanged.connect(self.onRatioChange)

        # Vertical Resolution
        self.vResLabel = QLabel('Pixel Height:')
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
        self.resGroupBox = QGroupBox("Resolution")
        self.resGroupBox.setLayout(self.resLayout)

    def undo(self):

        self.statusBar().showMessage('Generating Plot...')
        QApplication.processEvents()

        self.model.undo()
        self.showCurrentPlot()
        self.updateControls(self.model.activePlot)
        self.colorDialog.updateDialogValues()

        if not self.model.previousPlots:
            self.undoAction.setDisabled(True)

        self.redoAction.setDisabled(False)

    def redo(self):

        self.statusBar().showMessage('Generating Plot...')
        QApplication.processEvents()

        self.model.redo()
        self.showCurrentPlot()
        self.updateControls(self.model.activePlot)
        self.colorDialog.updateDialogValues()


        if not self.model.subsequentPlots:
            self.redoAction.setDisabled(True)

        self.undoAction.setDisabled(False)

    def saveImage(self):
        filename, ext = QFileDialog.getSaveFileName(self, "Save Plot Image",
                                            "untitled", "Images (*.png *.ppm)")
        if filename:
            if "." not in filename:
                self.pixmap.save(filename + ".png")
            else:
                self.pixmap.save(filename)

            mainWindow.statusBar().showMessage('Plot Image Saved', 5000)

    def restoreDefault(self):

        if self.model.currentPlot != self.model.getDefaultPlot():

            self.statusBar().showMessage('Generating Plot...')
            QApplication.processEvents()

            self.model.storeCurrent()
            self.model.activePlot = self.model.getDefaultPlot()
            self.model.generatePlot()
            self.showCurrentPlot()
            self.updateControls(self.model.activePlot)
            self.colorDialog.updateDialogValues()

            self.model.subsequentPlots = []

    def editBasis(self, basis):
        self.basis.setCurrentText(basis)
        self.applyChanges()

    def editColorBy(self, domain_kind):
        self.colorby.setCurrentText(domain_kind)
        self.applyChanges()

    def applyChanges(self):

        self.plotIm.setFocus()

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

        self.model.activePlot['highlightalpha'] = self.colorDialog.alphaBox.value()
        self.model.activePlot['highlightseed'] = self.colorDialog.seedBox.value()

        # Check that active plot is different from current plot
        if self.model.activePlot != self.model.currentPlot:

            self.statusBar().showMessage('Generating Plot...')
            QApplication.processEvents()

            self.model.storeCurrent()

            # Clear subsequentPlots
            self.model.subsequentPlots = []

            # Update plot.xml and display image
            self.model.generatePlot()
            self.showCurrentPlot()

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

        self.showStatusPlot()

    def toggleColorBy(self):

        colorby = self.colorby.currentText()
        self.colorDialog.colorbyBox.setCurrentText(colorby)

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

    def showStatusPlot(self):
        cp = self.model.currentPlot
        message = (f"Current Plot: ({round(cp['xOr'], 2)}, {round(cp['yOr'], 2)}, {round(cp['zOr'], 2)})  |  "
            f"{cp['width']} x {cp['height']}  |  {cp['basis']} basis | "
            f"color by {cp['colorby']}")
        self.statusBar().showMessage(message, 5000)

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

    def showColorDialog(self):
        self.colorDialog.show()
        self.colorDialog.raise_()
        self.colorDialog.activateWindow()

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

        self.menu = QMenu(self)

    def updateScale(self):
        # Determine Scale of image / plot
        scale = (self.model.currentPlot['hRes'] /
                 self.model.currentPlot['width'],
                 self.model.currentPlot['vRes'] /
                 self.model.currentPlot['height'])
        return scale

    def enterEvent(self, event):
        self.setCursor(QtCore.Qt.CrossCursor)
        mainWindow.coordLabel.show()

    def leaveEvent(self, event):
        mainWindow.showStatusPlot()
        mainWindow.coordLabel.hide()

    def mousePressEvent(self, event):

        cp = self.model.currentPlot

        # Cursor position in pixels relative to center of plot image
        xPos = event.pos().x() - (cp['hRes'] / 2)
        yPos = -event.pos().y() + (cp['vRes'] / 2)

        # Curson position in plot units relative to model
        self.xBandOrigin = (xPos / self.scale[0]) + cp[self.basisX[0]]
        self.yBandOrigin = (yPos / self.scale[1]) + cp[self.basisY[0]]

        # Rubber band start position
        self.bandOrigin = event.pos()

        # Create rubber band
        self.rubberBand.setGeometry(QtCore.QRect(self.bandOrigin, QtCore.QSize()))

        QLabel.mousePressEvent(self, event)

    def mouseDoubleClickEvent(self, event):

        cp = self.model.currentPlot

        # Cursor position in pixels relative to center of plot image
        xPos = event.pos().x() - (cp['hRes'] / 2)
        yPos = -event.pos().y() + (cp['vRes'] / 2)

        # Curson position in plot units relative to model
        xCenter = (xPos / self.scale[0]) + cp[self.basisX[0]]
        yCenter = (yPos / self.scale[1]) + cp[self.basisY[0]]

        self.basisX[1].setText(str(round(xCenter, 9)))
        self.basisY[1].setText(str(round(yCenter, 9)))
        mainWindow.applyChanges()

    def mouseMoveEvent(self, event):

        id, domain, domain_kind = self.getIDinfo(event)

        cp = self.model.currentPlot

        # Cursor position in pixels relative to center of image
        xPos = event.pos().x() - (cp['hRes'] / 2) #+ 1
        yPos = (-event.pos().y() + (cp['vRes'] / 2)) #+ 1

        # Cursor position in plot units relative to model
        xPlotPos = (xPos / self.scale[0]) + cp[self.basisX[0]]
        yPlotPos = (yPos / self.scale[1]) + cp[self.basisY[0]]

        # Show Cursor position relative to plot in status bar
        xyPos = f"({round(xPlotPos, 2)}, {round(yPlotPos, 2)}, {round(cp['zOr'], 2)})"
        xzPos = f"({round(xPlotPos, 2)}, {round(cp['yOr'], 2)}, {round(yPlotPos, 2)})"
        yzPos = f"({round(cp['xOr'], 2)}, {round(xPlotPos, 2)}, {round(yPlotPos, 2)})"

        if id != '-1':
            if domain[id]['name']:
                domainInfo = f"{domain_kind} {id}: {domain[id]['name']}"
            else:
                domainInfo = f"{domain_kind} {id}"
        else:
            domainInfo = ""

        mainWindow.statusBar().showMessage(f" {domainInfo}")

        if cp['basis'] == 'xy':
            mainWindow.coordLabel.setText(f'{xyPos}')
        elif cp['basis'] == 'xz':
            mainWindow.coordLabel.setText(f'{xzPos}')
        else:
            mainWindow.coordLabel.setText(f'{yzPos}')

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

            modifiers = QApplication.keyboardModifiers()

            # Zoom in to rubber band rectangle if left button held
            if app.mouseButtons() == QtCore.Qt.LeftButton and modifiers != QtCore.Qt.ShiftModifier:

                # Update width and height
                mainWindow.width.setValue(abs(self.xBandOrigin - xPlotPos))
                mainWindow.height.setValue(abs(self.yBandOrigin - yPlotPos))

            # Zoom out
            else:

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

    def contextMenuEvent(self, event):

        self.menu.clear()

        id, domain, domain_kind = self.getIDinfo(event)

        if id != '-1':

            domainID = self.menu.addAction(f"{domain_kind} {id}")
            domainID.setDisabled(True)

            if domain[id]['name']:
                domainName = self.menu.addAction(domain[id]['name'])
                domainName.setDisabled(True)

            self.menu.addSeparator()

            colorAction = self.menu.addAction(f'Edit {domain_kind} Color...')
            colorAction.triggered.connect(lambda :
                                    self.editDomainColor(id, domain_kind))

            maskAction = self.menu.addAction(f'Mask {domain_kind}')
            maskAction.setCheckable(True)
            maskAction.setChecked(domain[id]['masked'])
            maskAction.setDisabled(not self.model.activePlot['mask'])
            maskAction.triggered[bool].connect(lambda bool=bool:
                                    self.toggleMask(bool, id, domain_kind))

            highlightAction = self.menu.addAction(f'Highlight {domain_kind}')
            highlightAction.setCheckable(True)
            highlightAction.setChecked(domain[id]['highlighted'])
            highlightAction.setDisabled(not self.model.activePlot['highlight'])
            highlightAction.triggered[bool].connect(lambda bool=bool:
                                    self.toggleHL(bool, id, domain_kind))

        else:
            bgColorAction = self.menu.addAction('Edit Background Color...')
            bgColorAction.triggered.connect(self.editBGColor)

        self.menu.addSeparator()
        self.menu.addAction(mainWindow.saveAction)
        self.menu.addSeparator()

        basisMenu = self.menu.addMenu('&Basis')

        xyAction = basisMenu.addAction('xy')
        xyAction.setCheckable(True)
        xyAction.setChecked(self.model.currentPlot['basis'] == 'xy')
        xyAction.triggered.connect(lambda : mainWindow.editBasis('xy'))
        xzAction = basisMenu.addAction('xz')
        xzAction.setCheckable(True)
        xzAction.setChecked(self.model.currentPlot['basis'] == 'xz')
        xzAction.triggered.connect(lambda : mainWindow.editBasis('xz'))
        yzAction = basisMenu.addAction('yz')
        yzAction.setCheckable(True)
        yzAction.setChecked(self.model.currentPlot['basis'] == 'yz')
        yzAction.triggered.connect(lambda : mainWindow.editBasis('yz'))

        colorbyMenu = self.menu.addMenu('&Color By')

        cellAction = colorbyMenu.addAction('Cell')
        cellAction.setCheckable(True)
        cellAction.setChecked(self.model.currentPlot['colorby'] == 'cell')
        cellAction.triggered.connect(lambda : mainWindow.editColorBy('cell'))
        matAction = colorbyMenu.addAction('Material')
        matAction.setCheckable(True)
        matAction.setChecked(self.model.currentPlot['colorby'] == 'material')
        matAction.triggered.connect(lambda : mainWindow.editColorBy('material'))

        if not mainWindow.optionsDock.isVisible():
            self.menu.addSeparator()
            dockAction = self.menu.addAction('Show Options &Dock')
            dockAction.setShortcut('Ctrl+D')
            dockAction.triggered.connect(lambda : mainWindow.optionsDock.setVisible(True))

        self.menu.exec_(event.globalPos())

    def toggleMask(self, bool, id, domain_kind):

        if domain_kind == 'Cell':
            self.model.activePlot['cells'][id]['masked'] = bool
        else:
            self.model.activePlot['materials'][id]['masked'] = bool

        mainWindow.applyChanges()
        mainWindow.colorDialog.updateDialogValues()

    def toggleHL(self, bool, id, domain_kind):

        if domain_kind == 'Cell':
            self.model.activePlot['cells'][id]['highlighted'] = bool
        else:
            self.model.activePlot['materials'][id]['highlighted'] = bool

        mainWindow.applyChanges()
        mainWindow.colorDialog.updateDialogValues()

    def editDomainColor(self, id, domain_kind):
        mainWindow.colorDialog.editDomainColor(id, domain_kind)
        mainWindow.applyChanges()

    def editBGColor(self):
        mainWindow.colorDialog.editBackgroundColor()
        mainWindow.applyChanges()

    def getIDinfo(self, event):

        if event.pos().y() < self.model.currentPlot['vRes'] \
            and event.pos().x() < self.model.currentPlot['hRes']:
            id = f"{self.model.ids[event.pos().y()][event.pos().x()]}"
        else:
            id = '-1'

        if self.model.currentPlot['colorby'] == 'cell':
            domain = self.model.currentPlot['cells']
            domain_kind = 'Cell'
        else:
            domain = self.model.currentPlot['materials']
            domain_kind = 'Material'

        return id, domain, domain_kind

class ColorDialog(QDialog):
    def __init__(self, model, applyChanges, parent=None):
        super(ColorDialog, self).__init__(parent)

        self.setWindowTitle('Advanced Color Options')

        #self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.model = model
        self.applyChanges = applyChanges

        self.matColorButtons = {}
        self.matColorLabels = {}
        self.matMaskedChecks = {}
        self.matHighlightChecks = {}

        self.cellColorButtons = {}
        self.cellColorLabels = {}
        self.cellMaskedChecks = {}
        self.cellHighlightChecks = {}

        self.colorHeaders = {}
        self.maskHeaders = {}
        self.highlightHeaders = {}

        self.createDialogLayout()

    def createDialogLayout(self):

        self.colorDialogLayout = QVBoxLayout()

        # Tabs
        self.tabs = QTabWidget()
        self.cellTab = self.createDomainTab('Cell')
        self.matTab = self.createDomainTab('Material')
        self.generalTab = self.createGeneralTab()
        self.tabs.addTab(self.generalTab, 'General')
        self.tabs.addTab(self.cellTab, 'Cells')
        self.tabs.addTab(self.matTab, 'Materials')

        self.createButtonBox()

        self.colorDialogLayout.addWidget(self.tabs)
        self.colorDialogLayout.addStretch(1)
        self.colorDialogLayout.addWidget(self.buttonBox)

        self.updateDialogValues()

        self.setLayout(self.colorDialogLayout)

    def createGeneralTab(self):

        # Masking options
        self.maskCheck = QCheckBox('')
        self.maskCheck.stateChanged.connect(self.toggleMask)

        self.maskColorButton = QPushButton()
        self.maskColorButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.maskColorButton.setFixedWidth(FM.width("XXXXXXXXXX"))
        self.maskColorButton.setFixedHeight(FM.height() * 1.5)
        self.maskColorButton.clicked.connect(self.editMaskColor)

        self.maskColorRGB = QLabel(str(self.model.currentPlot['maskbg']))
        self.maskColorRGB.setMinimumWidth(FM.width("(XXX, XXX, XXX)"))
        maskColorLayout = QHBoxLayout()
        maskColorLayout.addWidget(self.maskColorButton)
        #maskColorLayout.addWidget(self.maskColorRGB)
        maskColorLayout.addStretch(1)

        # Highlighting options
        self.hlCheck = QCheckBox('')
        self.hlCheck.stateChanged.connect(self.toggleHL)

        self.hlColorButton = QPushButton()
        self.hlColorButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.hlColorButton.setFixedWidth(FM.width("XXXXXXXXXX"))
        self.hlColorButton.setFixedHeight(FM.height() * 1.5)
        self.hlColorButton.clicked.connect(self.editHighlightColor)

        self.hlColorRGB = QLabel(str(self.model.currentPlot['highlightbg']))
        self.hlColorRGB.setMinimumWidth(FM.width("(XXX, XXX, XXX)"))
        hlLayout = QHBoxLayout()
        hlLayout.addWidget(self.hlColorButton)
        #hlLayout.addWidget(self.hlColorRGB)
        hlLayout.addStretch(1)

        self.alphaBox = QDoubleSpinBox()
        self.alphaBox.setRange(0, 1)
        self.alphaBox.setSingleStep(.05)
        self.alphaBox.setValue(self.model.currentPlot['highlightalpha'])
        alphaLayout = QHBoxLayout()
        alphaLayout.addWidget(self.alphaBox)
        alphaLayout.addStretch(1)

        self.seedBox = QSpinBox()
        self.seedBox.setRange(1, 999)
        self.seedBox.setValue(self.model.currentPlot['highlightseed'])
        seedLayout = QHBoxLayout()
        seedLayout.addWidget(self.seedBox)
        seedLayout.addStretch(1)

        # General options
        self.bgButton = QPushButton()
        self.bgButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.bgButton.setFixedWidth(FM.width("XXXXXXXXXX"))
        self.bgButton.setFixedHeight(FM.height() * 1.5)
        self.bgButton.clicked.connect(self.editBackgroundColor)

        self.bgLabelRGB = QLabel(str(self.model.currentPlot['plotbackground']))
        self.bgLabelRGB.setMinimumWidth(FM.width("(XXX, XXX, XXX)"))
        bgLayout = QHBoxLayout()
        bgLayout.addWidget(self.bgButton)
        #bgLayout.addWidget(self.bgLabelRGB)
        bgLayout.addStretch(1)

        self.colorbyBox = QComboBox(self)
        self.colorbyBox.addItem("material")
        self.colorbyBox.addItem("cell")
        self.colorbyBox.currentTextChanged.connect(self.toggleColorBy)

        formLayout = QFormLayout()
        formLayout.setAlignment(QtCore.Qt.AlignHCenter)
        formLayout.setFormAlignment(QtCore.Qt.AlignHCenter)
        #formLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        formLayout.setLabelAlignment(QtCore.Qt.AlignLeft)

        formLayout.addRow('Masking:', self.maskCheck)
        formLayout.addRow('Mask Color:', maskColorLayout)
        formLayout.addRow(HorizontalLine())
        formLayout.addRow('Highlighting:', self.hlCheck)
        formLayout.addRow('Highlight Color:', hlLayout)
        formLayout.addRow('Highlight Alpha:', alphaLayout)
        formLayout.addRow('Highlight Seed:', seedLayout)
        formLayout.addRow(HorizontalLine())
        formLayout.addRow('Background Color:', bgLayout)
        formLayout.addRow('Color Plot By:', self.colorbyBox)
        #formLayout.addStretch(1)

        generalTab = QWidget()
        generalLayout = QHBoxLayout()

        innerWidget = QWidget()
        innerWidget.setLayout(formLayout)

        generalLayout.addStretch(1)
        generalLayout.addWidget(innerWidget)
        generalLayout.addStretch(1)

        generalTab.setLayout(generalLayout)

        return generalTab

    def createDomainTab(self, kind):

        domainTab = QScrollArea()
        domainTab.setAlignment(QtCore.Qt.AlignHCenter)
        domainTab.setMinimumHeight(100)
        #domainTab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        gridWidget = QWidget()
        gridLayout = QGridLayout()
        gridLayout.setAlignment(QtCore.Qt.AlignCenter)
        gridLayout.setVerticalSpacing(9)

        if kind == 'Cell':
            domain = self.model.activePlot['cells']
            groups = [self.cellColorButtons, self.cellColorLabels,
                      self.cellMaskedChecks, self.cellHighlightChecks]
        else:
            domain = self.model.activePlot['materials']
            groups = [self.matColorButtons, self.matColorLabels,
                      self.matMaskedChecks, self.matHighlightChecks]

        idHeader = QLabel('ID:')
        nameHeader = QLabel('Name:')
        colorHeader = QLabel('Custom Color (RGB):')
        maskHeader = QLabel('Mask:')
        highlightHeader = QLabel('Highlight:')

        #for header in (idHeader, nameHeader, colorHeader, maskHeader, highlightHeader):
        #    header.setStyleSheet("font: bold")

        self.colorHeaders[kind] = colorHeader
        self.maskHeaders[kind] = maskHeader
        self.highlightHeaders[kind] = highlightHeader

        gridLayout.addWidget(idHeader, 0, 0)
        gridLayout.addWidget(nameHeader, 0, 1)
        gridLayout.addWidget(colorHeader, 0, 2, 1, 2)
        gridLayout.addWidget(maskHeader, 0, 4)
        gridLayout.addWidget(highlightHeader, 0, 5)

        row = 2
        for id, attr in domain.items():

            # Horizontal Line
            gridLayout.addWidget(HorizontalLine(), row-1, 0, 1, 6)

            # ID Label
            idLabel = QLabel(id)
            idLabel.setMinimumWidth(FM.width("999"))

            # Name Label
            if attr['name']:
                nameLabel = QLabel(attr['name'])
            else: nameLabel = QLabel(f'{kind} {id}')
            nameLabel.setMinimumWidth(FM.width("XXXXXXXXXX"))

            # Color Button
            button = QPushButton(" ")
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setFixedWidth(FM.width("XXXXX"))
            button.setFixedHeight(FM.height() * 1.5)
            button.setStyleSheet("margin-left: 5px")
            button.clicked.connect(lambda id=id, kind=kind:
                                   self.editDomainColor(id, kind))
            groups[0][id] = button

            # Color Label
            label = QLabel('--')
            label.setMinimumWidth(FM.width("X(999, 999, 999)"))
            groups[1][id] = label

            # Masked Check
            maskedcheck = QCheckBox()
            maskedcheck.stateChanged.connect(lambda state, id=id, kind=kind:
                                        self.toggleDomainMask(state, id, kind))
            groups[2][id] = maskedcheck

            # Highlight Check
            hlcheck = QCheckBox()
            hlcheck.stateChanged.connect(lambda state, id=id, kind=kind:
                                        self.toggleDomainHL(state, id, kind))
            groups[3][id] = hlcheck

            # Layout Row
            gridLayout.addWidget(idLabel, row, 0)
            gridLayout.addWidget(nameLabel, row, 1)
            gridLayout.addWidget(button, row, 2, QtCore.Qt.AlignVCenter)
            gridLayout.addWidget(label, row, 3)
            gridLayout.addWidget(maskedcheck, row, 4, QtCore.Qt.AlignCenter)
            gridLayout.addWidget(hlcheck, row, 5, QtCore.Qt.AlignCenter)
            row += 2

        gridWidget.setLayout(gridLayout)
        domainTab.setWidget(gridWidget)

        return domainTab

    def createButtonBox(self):
        self.buttonBox = QWidget()
        buttonLayout = QHBoxLayout()
        applyButton = QPushButton("Apply Changes")
        closeButton = QPushButton("Close")
        applyButton.clicked.connect(self.applyChanges)
        closeButton.clicked.connect(self.hide)
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(applyButton)
        buttonLayout.addWidget(closeButton)
        self.buttonBox.setLayout(buttonLayout)

    def toggleMask(self):

        checked = self.maskCheck.isChecked()

        if checked:
            self.maskCheck.setText('Enabled')
        else:
            self.maskCheck.setText('Disabled')

        self.model.activePlot['mask'] = checked
        for header in self.maskHeaders.values():
            header.setDisabled(not checked)
        for check in self.matMaskedChecks.values():
            check.setDisabled(not checked)
        for check in self.cellMaskedChecks.values():
            check.setDisabled(not checked)

        self.raise_()
        self.activateWindow()

    def toggleHL(self):

        checked = self.hlCheck.isChecked()

        if checked:
            self.hlCheck.setText('Enabled')
        else:
            self.hlCheck.setText('Disabled')

        self.model.activePlot['highlight'] = checked
        for header in self.highlightHeaders.values():
            header.setDisabled(not checked)
        for check in self.matHighlightChecks.values():
            check.setDisabled(not checked)
        for check in self.cellHighlightChecks.values():
            check.setDisabled(not checked)


        self.raise_()
        self.activateWindow()

    def editMaskColor(self):
        current_color = self.model.activePlot['maskbg']
        dlg = QColorDialog(self)
        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec_():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activePlot['maskbg'] = new_color
            self.maskColorButton.setStyleSheet("border-radius: 10px;"
                                "background-color: rgb%s" % (str(new_color)))
            self.maskColorRGB.setText(str(new_color))

        self.raise_()
        self.activateWindow()

    def editHighlightColor(self):
        current_color = self.model.activePlot['highlightbg']
        dlg = QColorDialog(self)
        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec_():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activePlot['highlightbg'] = new_color
            self.hlColorButton.setStyleSheet("border-radius: 10px;"
                                "background-color: rgb%s" % (str(new_color)))
            self.hlColorRGB.setText(str(new_color))

        self.raise_()
        self.activateWindow()

    def editBackgroundColor(self):
        current_color = self.model.activePlot['plotbackground']
        dlg = QColorDialog(self)
        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec_():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activePlot['plotbackground'] = new_color
            self.bgButton.setStyleSheet("border-radius: 10px;"
                                "background-color: rgb%s" % (str(new_color)))
            self.bgLabelRGB.setText(str(new_color))
        self.raise_()
        self.activateWindow()

    def toggleColorBy(self):
        selection = self.colorbyBox.currentText()
        mainWindow.colorby.setCurrentText(selection)

        self.raise_()
        self.activateWindow()

    def editDomainColor(self, id, kind):

        if kind == 'Cell':
            domain = self.model.activePlot['cells']
            buttons = self.cellColorButtons
            labels = self.cellColorLabels
        else:
            domain = self.model.activePlot['materials']
            buttons = self.matColorButtons
            labels = self.matColorLabels

        current_color = domain[id]['color']
        dlg = QColorDialog(self)

        if current_color is not None:
            dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec_():
            new_color = dlg.currentColor().getRgb()[:3]
            domain[id]['color'] = new_color
            buttons[id].setText("")
            buttons[id].setStyleSheet("margin-left: 3px;"
                                      "border-radius: 10px;"
                                      "background-color: rgb%s" % (str(new_color)))
            labels[id].setText(str(new_color))

        self.raise_()
        self.activateWindow()

    def toggleDomainMask(self, state, id, kind):

        if kind == 'Cell':
            domain = self.model.activePlot['cells']
        else:
            domain = self.model.activePlot['materials']

        if state == QtCore.Qt.Checked:
            domain[id]['masked'] = True
        else:
            domain[id]['masked'] = False

    def toggleDomainHL(self, state, id, kind):

        if kind == 'Cell':
            domain = self.model.activePlot['cells']
        else:
            domain = self.model.activePlot['materials']

        if state == QtCore.Qt.Checked:
            domain[id]['highlighted'] = True
        else:
            domain[id]['highlighted'] = False

        self.raise_()
        self.activateWindow()

    def updateDialogValues(self):

        # Update General Tab
        self.maskCheck.setChecked(self.model.activePlot['mask'])
        self.toggleMask()
        mask_color = self.model.activePlot['maskbg']
        self.maskColorButton.setStyleSheet("border-radius: 10px;"
                                "background-color: rgb%s" % (str(mask_color)))
        self.maskColorRGB.setText(str(mask_color))

        self.hlCheck.setChecked(self.model.activePlot['highlight'])
        self.toggleHL()
        hl_color = self.model.activePlot['highlightbg']
        self.hlColorButton.setStyleSheet("border-radius: 10px;"
                                    "background-color: rgb%s" % (str(hl_color)))
        self.hlColorRGB.setText(str(hl_color))
        self.alphaBox.setValue(self.model.activePlot['highlightalpha'])
        self.seedBox.setValue(self.model.activePlot['highlightseed'])

        bg_color = self.model.activePlot['plotbackground']
        self.bgButton.setStyleSheet("border-radius: 10px;"
                                    "background-color: rgb%s" % (str(bg_color)))
        self.bgLabelRGB.setText(str(bg_color))

        self.colorbyBox.setCurrentText(self.model.activePlot['colorby'])

        # Update Cell Colors
        for id, button in self.cellColorButtons.items():
            color = self.model.activePlot['cells'][id]['color']
            if color:
                button.setText(" ")
                button.setStyleSheet("margin-left: 3px;"
                                     "border-radius: 10px;"
                                     "background-color: rgb%s" % (str(color)))
            else:
                button.setText("-")
                button.setStyleSheet("font: 16px;"
                                     "text-align: center center;"
                                     "color: lightgrey; margin-left: 3px;"
                                     "border-radius: 10px;"
                                     "background-color: 'grey'")

        for id, label in self.cellColorLabels.items():
            color = self.model.activePlot['cells'][id]['color']
            if color:
                label.setText(str(color))
            else:
                label.setText('--')

        # Update Material Colors
        for id, button in self.matColorButtons.items():
            color = self.model.activePlot['materials'][id]['color']
            if color:
                button.setText(" ")
                button.setStyleSheet("margin-left: 3px;"
                                     "border-radius: 10px;"
                                     "background-color: rgb%s" % (str(color)))
            else:
                button.setText("-")
                button.setStyleSheet("font: 16px;"
                                     "text-align: center center;"
                                     "color: lightgrey; margin-left: 3px;"
                                     "border-radius: 10px;"
                                     "background-color: 'grey'")

        for id, label in self.matColorLabels.items():
            color = self.model.activePlot['materials'][id]['color']
            if color:
                label.setText(str(color))
            else:
                label.setText('--')

        # Update Cell Checks
        self.updateChecks(self.model.activePlot['cells'])
        self.updateChecks(self.model.activePlot['materials'])

    def updateChecks(self, domain):
        if domain == self.model.activePlot['cells']:
            groups = [self.cellMaskedChecks, self.cellHighlightChecks]
        else:
            groups = [self.matMaskedChecks, self.matHighlightChecks]

        for id, checkbox in groups[0].items():
            if domain[id]['masked']:
                checkbox.setChecked(True)
            else:
                checkbox.setChecked(False)

        for id, checkbox in groups[1].items():
            if domain[id]['highlighted']:
                checkbox.setChecked(True)
            else:
                checkbox.setChecked(False)

class HorizontalLine(QFrame):
    def __init__(self):
        super(HorizontalLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setContentsMargins(0,4,0,0)
        self.setStyleSheet("padding: 0px")

class ColorButton(QWidget):
    pass

if __name__ == '__main__':

    app = QApplication(sys.argv)
    FM = QtGui.QFontMetricsF(app.font())
    app.setWindowIcon(QtGui.QIcon('openmc_logo.png'))
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
