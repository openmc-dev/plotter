#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, openmc, copy, time
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import (QApplication, QLabel, QSizePolicy, QMainWindow,
    QScrollArea, QMenu, QAction, QFileDialog, QColorDialog)
from plotmodel import PlotModel, PlotView, Domain
from plotgui import PlotImage, ColorDialog, OptionsDock

class MainWindow(QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()

        # Set Window Title
        self.setWindowTitle('OpenMC Plot Explorer')
        self.move(100,100)

        # Create model

        self.model = PlotModel()
        self.scale = (1, 1)

        # Create plot image

        self.plotIm = PlotImage(self.model, self, FM)
        self.frame = QScrollArea(self)
        self.frame.setAlignment(QtCore.Qt.AlignCenter)
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.frame.setWidget(self.plotIm)
        self.setCentralWidget(self.frame)

        # Create Dock
        self.dock = OptionsDock(self.model, self, FM)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock)

        # Initiate color dialog
        self.colorDialog = ColorDialog(self.model, self, FM, self)
        self.colorDialog.move(600, 200)
        self.colorDialog.hide()

        # Create menubar
        self.createMenuBar()

        # Load Plot
        self.model.generatePlot()
        self.showcurrentView()
        self.dock.updateDock()
        self.colorDialog.updateDialogValues()

        # Status Bar
        self.coordLabel = QLabel()
        self.statusBar().addPermanentWidget(self.coordLabel)
        self.coordLabel.hide()

    ''' Create / Update Menus '''

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

        self.restoreAction = QAction("&Restore Default Plot", self)
        self.restoreAction.setShortcut("Ctrl+R")
        self.restoreAction.triggered.connect(self.restoreDefault)

        self.editMenu.addAction(self.applyAction)
        self.editMenu.addSeparator()
        self.editMenu.addAction(self.undoAction)
        self.editMenu.addAction(self.redoAction)
        self.editMenu.addSeparator()
        self.editMenu.addAction(self.restoreAction)
        self.editMenu.addSeparator()
        self.editMenu.aboutToShow.connect(self.updateEditMenu)

        # Edit -> Basis Menu
        self.xyAction = QAction('&xy  ', self)
        self.xyAction.setCheckable(True)
        self.xyAction.setShortcut('Alt+X')
        self.xyAction.triggered.connect(lambda :
            self.editBasis('xy', apply=True))

        self.xzAction = QAction('x&z  ', self)
        self.xzAction.setCheckable(True)
        self.xzAction.setShortcut('Alt+Z')
        self.xzAction.triggered.connect(lambda :
            self.editBasis('xz', apply=True))

        self.yzAction = QAction('&yz  ', self)
        self.yzAction.setCheckable(True)
        self.yzAction.setShortcut('Alt+Y')
        self.yzAction.triggered.connect(lambda :
            self.editBasis('yz', apply=True))

        self.basisMenu = self.editMenu.addMenu('&Basis')
        self.basisMenu.addAction(self.xyAction)
        self.basisMenu.addAction(self.xzAction)
        self.basisMenu.addAction(self.yzAction)
        self.basisMenu.aboutToShow.connect(self.updateBasisMenu)

        # Edit -> Color By Menu
        self.cellAction = QAction('&Cell', self)
        self.cellAction.setCheckable(True)
        self.cellAction.setShortcut('Alt+C')
        self.cellAction.triggered.connect(lambda :
            self.editColorBy('cell', apply=True))

        self.materialAction = QAction('&Material', self)
        self.materialAction.setCheckable(True)
        self.materialAction.setShortcut('Alt+M')
        self.materialAction.triggered.connect(lambda :
            self.editColorBy('material', apply=True))

        self.colorbyMenu = self.editMenu.addMenu('&Color By')
        self.colorbyMenu.addAction(self.cellAction)
        self.colorbyMenu.addAction(self.materialAction)
        self.colorbyMenu.aboutToShow.connect(self.updateColorbyMenu)

        self.editMenu.addSeparator()

        self.maskingAction = QAction('Enable &Masking', self)
        self.maskingAction.setShortcut('Ctrl+M')
        self.maskingAction.setCheckable(True)
        self.maskingAction.triggered[bool].connect(lambda bool=bool:
            self.toggleMasking(bool, apply=True))
        self.editMenu.addAction(self.maskingAction)

        self.highlightingAct = QAction('Enable High&lighting', self)
        self.highlightingAct.setShortcut('Ctrl+L')
        self.highlightingAct.setCheckable(True)
        self.highlightingAct.triggered[bool].connect(lambda bool=bool:
            self.toggleHighlighting(bool, apply=True))
        self.editMenu.addAction(self.highlightingAct)

        # View Menu
        self.viewMenu = self.mainMenu.addMenu('&View')
        self.dockAction = QAction('Hide Options &Dock', self)
        self.dockAction.setShortcut("Ctrl+D")
        self.dockAction.triggered.connect(self.toggleDockView)
        self.viewMenu.addAction(self.dockAction)
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

    def updateEditMenu(self):

        changed = self.model.currentView != self.model.defaultView
        self.restoreAction.setDisabled(not changed)

        self.maskingAction.setChecked(self.model.currentView.masking)
        self.highlightingAct.setChecked(self.model.currentView.highlighting)

    def updateBasisMenu(self):

        self.xyAction.setChecked(self.model.currentView.basis == 'xy')
        self.xzAction.setChecked(self.model.currentView.basis == 'xz')
        self.yzAction.setChecked(self.model.currentView.basis == 'yz')

    def updateColorbyMenu(self):

        self.cellAction.setChecked(self.model.currentView.colorby == 'cell')
        self.materialAction.setChecked(self.model.currentView.colorby == 'material')

    def updateViewMenu(self):

        if self.dock.isVisible():
            self.dockAction.setText('Hide Options &Dock')
        else:
            self.dockAction.setText('Show Options &Dock')

    def updateWindowMenu(self):

        self.colorDialogAction.setChecked(self.colorDialog.isActiveWindow())
        self.mainWindowAction.setChecked(self.isActiveWindow())

    ''' Menu and Shared Methods '''

    def saveImage(self):
        filename, ext = QFileDialog.getSaveFileName(self, "Save Plot Image",
                                            "untitled", "Images (*.png *.ppm)")
        if filename:
            if "." not in filename:
                self.pixmap.save(filename + ".png")
            else:
                self.pixmap.save(filename)

            mainWindow.statusBar().showMessage('Plot Image Saved', 5000)

    def applyChanges(self):

        self.plotIm.setFocus()

        # Check that active plot is different from current plot
        if self.model.activeView != self.model.currentView:

            self.statusBar().showMessage('Generating Plot...')
            QApplication.processEvents()

            self.model.storeCurrent()
            self.model.subsequentViews = []
            self.model.generatePlot()
            self.showcurrentView()

    def undo(self):

        self.statusBar().showMessage('Generating Plot...')
        QApplication.processEvents()

        self.model.undo()
        self.showcurrentView()
        self.dock.updateDock()
        self.colorDialog.updateDialogValues()

        if not self.model.previousViews:
            self.undoAction.setDisabled(True)

        self.redoAction.setDisabled(False)

    def redo(self):

        self.statusBar().showMessage('Generating Plot...')
        QApplication.processEvents()

        self.model.redo()
        self.showcurrentView()
        self.dock.updateDock()
        self.colorDialog.updateDialogValues()


        if not self.model.subsequentViews:
            self.redoAction.setDisabled(True)

        self.undoAction.setDisabled(False)

    def restoreDefault(self):

        if self.model.currentView != self.model.defaultView:

            self.statusBar().showMessage('Generating Plot...')
            QApplication.processEvents()

            self.model.storeCurrent()
            self.model.activeView = copy.deepcopy(self.model.defaultView)
            self.model.generatePlot()
            self.showcurrentView()
            self.dock.updateDock()
            self.colorDialog.updateDialogValues()

            self.model.subsequentViews = []

    def editBasis(self, basis, apply=False):

        self.model.activeView.basis = basis
        self.dock.updateBasis()

        if apply:
            self.applyChanges()

    def editColorBy(self, domain_kind, apply=False):

        self.model.activeView.colorby = domain_kind
        self.dock.updateColorBy()
        self.colorDialog.updateColorBy()

        if apply:
            self.applyChanges()

    def toggleMasking(self, state, apply=False):

        self.model.activeView.masking = bool(state)
        self.colorDialog.updateMasking()

        if apply:
            self.applyChanges()

    def toggleHighlighting(self, state, apply=False):

        self.model.activeView.highlighting = bool(state)
        self.colorDialog.updateHighlighting()

        if apply:
            self.applyChanges()

    def toggleDockView(self):

        #self.optionsDock.setVisible(not self.optionsDock.isVisible())
        if self.dock.isVisible():
            self.dock.hide()
        else:
            self.dock.setVisible(True)

        self.showMainWindow()

    def showMainWindow(self):
        self.raise_()
        self.activateWindow()

    def showColorDialog(self):
        self.colorDialog.show()
        self.colorDialog.raise_()
        self.colorDialog.activateWindow()

    ''' Dock Methods '''

    def editSingleOrigin(self, value, dimension):
        self.model.activeView.origin[dimension] = value

    def editWidth(self, value):
        self.model.activeView.width = value
        self.onRatioChange()
        self.dock.updateWidth()

    def editHeight(self, value):
        self.model.activeView.height = value
        self.onRatioChange()
        self.dock.updateHeight()

    def toggleAspectLock(self, state):
        self.model.activeView.aspectLock = bool(state)
        self.onRatioChange()
        self.dock.updateAspectLock()

    def editVRes(self, value):
        self.model.activeView.vRes = value
        self.dock.updateVRes()

    def editHRes(self, value):
        self.model.activeView.hRes = value
        self.onRatioChange()
        self.dock.updateHRes()

    ''' Color Dialog Methods '''

    def editMaskingColor(self):

        current_color = self.model.activeView.maskBackground
        dlg = QColorDialog(self)

        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec_():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activeView.maskBackground = new_color

        self.colorDialog.updateMaskingColor()

    def editHighlightColor(self):

        current_color = self.model.activeView.highlightBackground
        dlg = QColorDialog(self)

        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec_():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activeView.highlightBackground = new_color

        self.colorDialog.updateHighlightColor()

    def editAlpha(self, value):
        self.model.activeView.highlightAlpha = value

    def editSeed(self, value):
        self.model.activeView.highlightSeed = value

    def editBackgroundColor(self, apply=False):

        current_color = self.model.activeView.plotBackground
        dlg = QColorDialog(self)

        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec_():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activeView.plotBackground = new_color

        self.colorDialog.updateBackgroundColor()

        if apply:
            self.applyChanges()

    def editDomainColor(self, kind, id, apply=False):

        if kind == 'Cell':
            domain = self.model.activeView.cells
        else:
            domain = self.model.activeView.materials

        current_color = domain[id].color
        dlg = QColorDialog(self)

        if current_color is not None:
            dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec_():
            new_color = dlg.currentColor().getRgb()[:3]
            domain[id].color = new_color

        self.colorDialog.updateDomainColor(kind, id)

        if apply:
            self.applyChanges()

    def toggleDomainMask(self, state, kind, id, apply=False):

        if kind == 'Cell':
            domain = self.model.activeView.cells
        else:
            domain = self.model.activeView.materials

        domain[id].masked = bool(state)

        if apply:
            self.applyChanges()

        self.colorDialog.updateMask(kind, id)

    def toggleDomainHighlight(self, state, kind, id, apply=False):

        if kind == 'Cell':
            domain = self.model.activeView.cells
        else:
            domain = self.model.activeView.materials

        domain[id].highlighted = bool(state)
        self.colorDialog.updateHighlight(kind, id)

        if apply:
            self.applyChanges()

    ''' Plot Image Options '''

    def editPlotOrigin(self, xOr, yOr, zOr=None, apply=False):

        if zOr != None:
            self.model.activeView.origin = [xOr, yOr, zOr]
        else:
            self.model.activeView.origin[self.xBasis] = xOr
            self.model.activeView.origin[self.yBasis] = yOr

        self.dock.updateOrigin()

        if apply:
            self.applyChanges()

    def revertDockControls(self):
        self.dock.revertToCurrent()

    ''' Helper Methods '''

    def showcurrentView(self):

        self.updateScale()
        self.updateRelativeBases()

        # Update plot image
        self.pixmap = QtGui.QPixmap('plot.ppm')
        self.plotIm.setPixmap(self.pixmap)
        self.plotIm.adjustSize()

        self.adjustWindow()

        if self.model.previousViews:
            self.undoAction.setDisabled(False)

        if self.model.subsequentViews:
            self.redoAction.setDisabled(False)
        else:
            self.redoAction.setDisabled(True)

        self.showStatusPlot()

    def updateScale(self):

        cv = self.model.currentView
        self.scale = (cv.hRes / cv.width, cv.vRes / cv.height)

    def updateRelativeBases(self):

        # Determine image axes relative to plot bases
        cv = self.model.currentView
        self.xBasis = 0 if cv.basis[0] == 'x' else 1
        self.yBasis = 1 if cv.basis[1] == 'y' else 2

    def adjustWindow(self):
        # Get screen dimensions
        self.screen = app.desktop().screenGeometry()
        self.setMaximumSize(self.screen.width(), self.screen.height())

        # Adjust scroll area to fit plot if window will not exeed screen size
        if self.model.activeView.hRes < .8 * self.screen.width():
            self.frame.setMinimumWidth(self.plotIm.width() + 20)
        else:
            self.frame.setMinimumWidth(500)
        if self.model.activeView.vRes < .85 * self.screen.height():
            self.frame.setMinimumHeight(self.plotIm.height() + 20)
        else:
            self.frame.setMinimumHeight(500)

    def onRatioChange(self):
        av = self.model.activeView

        if av.aspectLock:
            ratio = av.width / max(av.height, .001)
            av.vRes = int(av.hRes / ratio)
            self.dock.updateVRes()

    def showStatusPlot(self):
        cv = self.model.currentView
        origin = (round(dimension, 2) for dimension in cv.origin)
        message = (f"Current Plot: {str(tuple(origin))}  |  "
                   f"{round(cv.width, 2)} x {round(cv.height, 2)}  | "
                   f"Basis: {cv.basis} | Color By: {cv.colorby}")
        self.statusBar().showMessage(message, 3000)

    def showCoords(self, xPlotPos, yPlotPos):

        cv = self.model.currentView

        if cv.basis == 'xy':
            coords = (f"({round(xPlotPos, 2)}, {round(yPlotPos, 2)}, "
                      f"{round(cv.origin[2], 2)})")
        elif cv.basis == 'xz':
            coords = (f"({round(xPlotPos, 2)}, {round(cv.origin[1], 2)}, "
                      f"{round(yPlotPos, 2)})")
        else:
            coords = (f"({round(cv.origin[0], 2)}, {round(xPlotPos, 2)}, "
                      f"{round(yPlotPos, 2)})")

        self.coordLabel.setText(f'{coords}')


if __name__ == '__main__':

    app = QApplication(sys.argv)
    FM = QtGui.QFontMetricsF(app.font())
    app.setWindowIcon(QtGui.QIcon('openmc_logo.png'))
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
