#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import copy
from functools import partial
import os
from pathlib import Path
import pickle
import sys
from threading import Thread
import time

import openmc
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import (QApplication, QLabel, QSizePolicy, QMainWindow,
                               QScrollArea, QMenu, QAction, QFileDialog,
                               QColorDialog, QInputDialog, QSplashScreen)

from plotmodel import PlotModel, DomainTableModel
from plotgui import PlotImage, ColorDialog, OptionsDock


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowTitle('OpenMC Plot Explorer')

    def loadGui(self):

        self.restored = False
        self.pixmap = None
        self.zoom = 100

        self.model = PlotModel()
        self.updateRelativeBases()
        self.restoreModelSettings()

        self.cellsModel = DomainTableModel(self.model.activeView.cells)
        self.materialsModel = DomainTableModel(self.model.activeView.materials)

        # Create viewing area
        self.frame = QScrollArea(self)
        self.frame.setAlignment(QtCore.Qt.AlignCenter)
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCentralWidget(self.frame)

        # Create plot image
        self.plotIm = PlotImage(self.model, self.frame, self)
        self.frame.setWidget(self.plotIm)

        # Dock
        self.dock = OptionsDock(self.model, FM, self)
        self.dock.setObjectName("OptionsDock")
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock)

        # Color Dialog
        self.colorDialog = ColorDialog(self.model, FM, self)
        self.colorDialog.hide()

        # Restore Window Settings
        self.restoreWindowSettings()

        # Create menubar
        self.createMenuBar()

        # Status Bar
        self.coord_label = QLabel()
        self.statusBar().addPermanentWidget(self.coord_label)
        self.coord_label.hide()

        # Load Plot
        self.statusBar().showMessage('Generating Plot...')
        self.dock.updateDock()
        self.colorDialog.updateDialogValues()

        if self.restored:
            self.showCurrentView()
        else:
            # Timer allows GUI to render before plot finishes loading
            QtCore.QTimer.singleShot(0, self.model.generatePlot)
            QtCore.QTimer.singleShot(0, self.showCurrentView)

    # Create and update menus:
    def createMenuBar(self):
        self.mainMenu = self.menuBar()

        # File Menu
        self.saveImageAction = QAction("&Save Image As...", self)
        self.saveImageAction.setShortcut("Ctrl+Shift+S")
        self.saveImageAction.setToolTip('Save plot image')
        self.saveImageAction.setStatusTip('Save plot image')
        self.saveImageAction.triggered.connect(self.saveImage)

        self.saveViewAction = QAction("Save &View Settings...", self)
        self.saveViewAction.setShortcut(QtGui.QKeySequence.Save)
        self.saveViewAction.setStatusTip('Save current view settings')
        self.saveViewAction.triggered.connect(self.saveView)

        self.openAction = QAction("&Open View Settings...", self)
        self.openAction.setShortcut(QtGui.QKeySequence.Open)
        self.openAction.setToolTip('Open saved view settings')
        self.openAction.setStatusTip('Open saved view settings')
        self.openAction.triggered.connect(self.openView)

        self.quitAction = QAction("&Quit", self)
        self.quitAction.setShortcut(QtGui.QKeySequence.Quit)
        self.quitAction.setToolTip('Quit OpenMC Plot Explorer')
        self.quitAction.setStatusTip('Quit OpenMC Plot Explorer')
        self.quitAction.triggered.connect(self.close)

        self.fileMenu = self.mainMenu.addMenu('&File')
        self.fileMenu.addAction(self.saveImageAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.saveViewAction)
        self.fileMenu.addAction(self.openAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.quitAction)

        # Edit Menu
        self.applyAction = QAction("&Apply Changes", self)
        self.applyAction.setShortcut("Ctrl+Return")
        self.applyAction.setToolTip('Generate new view with changes applied')
        self.applyAction.setStatusTip('Generate new view with changes applied')
        self.applyAction.triggered.connect(self.applyChanges)

        self.undoAction = QAction('&Undo', self)
        self.undoAction.setShortcut(QtGui.QKeySequence.Undo)
        self.undoAction.setToolTip('Undo')
        self.undoAction.setStatusTip('Undo last plot view change')
        self.undoAction.setDisabled(True)
        self.undoAction.triggered.connect(self.undo)

        self.redoAction = QAction('&Redo', self)
        self.redoAction.setDisabled(True)
        self.redoAction.setToolTip('Redo')
        self.redoAction.setStatusTip('Redo last plot view change')
        self.redoAction.setShortcut(QtGui.QKeySequence.Redo)
        self.redoAction.triggered.connect(self.redo)

        self.restoreAction = QAction("&Restore Default Plot", self)
        self.restoreAction.setShortcut("Ctrl+R")
        self.restoreAction.setToolTip('Restore to default plot view')
        self.restoreAction.setStatusTip('Restore to default plot view')
        self.restoreAction.triggered.connect(self.restoreDefault)

        self.editMenu = self.mainMenu.addMenu('&Edit')
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
        self.xyAction.setToolTip('Change to xy basis')
        self.xyAction.setStatusTip('Change to xy basis')
        xy_connector = partial(self.editBasis, 'xy', apply=True)
        self.xyAction.triggered.connect(xy_connector)

        self.xzAction = QAction('x&z  ', self)
        self.xzAction.setCheckable(True)
        self.xzAction.setShortcut('Alt+Z')
        self.xzAction.setToolTip('Change to xz basis')
        self.xzAction.setStatusTip('Change to xz basis')
        xz_connector = partial(self.editBasis, 'xz', apply=True)
        self.xzAction.triggered.connect(xz_connector)

        self.yzAction = QAction('&yz  ', self)
        self.yzAction.setCheckable(True)
        self.yzAction.setShortcut('Alt+Y')
        self.yzAction.setToolTip('Change to yz basis')
        self.yzAction.setStatusTip('Change to yz basis')
        yz_connector = partial(self.editBasis, 'yz', apply=True)
        self.yzAction.triggered.connect(yz_connector)

        self.basisMenu = self.editMenu.addMenu('&Basis')
        self.basisMenu.addAction(self.xyAction)
        self.basisMenu.addAction(self.xzAction)
        self.basisMenu.addAction(self.yzAction)
        self.basisMenu.aboutToShow.connect(self.updateBasisMenu)

        # Edit -> Color By Menu
        self.cellAction = QAction('&Cell', self)
        self.cellAction.setCheckable(True)
        self.cellAction.setShortcut('Alt+C')
        self.cellAction.setToolTip('Color by cell')
        self.cellAction.setStatusTip('Color plot by cell')
        cell_connector = partial(self.editColorBy, 'cell', apply=True)
        self.cellAction.triggered.connect(cell_connector)

        self.materialAction = QAction('&Material', self)
        self.materialAction.setCheckable(True)
        self.materialAction.setShortcut('Alt+M')
        self.materialAction.setToolTip('Color by material')
        self.materialAction.setStatusTip('Color plot by material')
        material_connector = partial(self.editColorBy, 'material', apply=True)
        self.materialAction.triggered.connect(material_connector)

        self.temperatureAction = QAction('&Temperature', self)
        self.temperatureAction.setCheckable(True)
        self.temperatureAction.setShortcut('Alt+T')
        self.temperatureAction.setToolTip('Color by temperature')
        self.temperatureAction.setStatusTip('Color plot by temperature')
        temp_connector = partial(self.editColorBy, 'temperature', apply=True)
        self.temperatureAction.triggered.connect(temp_connector)

        self.densityAction = QAction('&Density', self)
        self.densityAction.setCheckable(True)
        self.densityAction.setShortcut('Alt+D')
        self.densityAction.setToolTip('Color by density')
        self.densityAction.setStatusTip('Color plot by density')
        density_connector = partial(self.editColorBy, 'density', apply=True)
        self.densityAction.triggered.connect(density_connector)

        self.colorbyMenu = self.editMenu.addMenu('&Color By')
        self.colorbyMenu.addAction(self.cellAction)
        self.colorbyMenu.addAction(self.materialAction)
        self.colorbyMenu.addAction(self.temperatureAction)
        self.colorbyMenu.addAction(self.densityAction)

        self.colorbyMenu.aboutToShow.connect(self.updateColorbyMenu)

        self.editMenu.addSeparator()

        self.maskingAction = QAction('Enable &Masking', self)
        self.maskingAction.setShortcut('Ctrl+M')
        self.maskingAction.setCheckable(True)
        self.maskingAction.setToolTip('Toggle masking')
        self.maskingAction.setStatusTip('Toggle whether masking is enabled')
        masking_connector = partial(self.toggleMasking, apply=True)
        self.maskingAction.toggled.connect(masking_connector)
        self.editMenu.addAction(self.maskingAction)

        self.highlightingAct = QAction('Enable High&lighting', self)
        self.highlightingAct.setShortcut('Ctrl+L')
        self.highlightingAct.setCheckable(True)
        self.highlightingAct.setToolTip('Toggle highlighting')
        self.highlightingAct.setStatusTip('Toggle whether '
                                          'highlighting is enabled')
        highlight_connector = partial(self.toggleHighlighting, apply=True)
        self.highlightingAct.toggled.connect(highlight_connector)
        self.editMenu.addAction(self.highlightingAct)

        # View Menu
        self.dockAction = QAction('Hide &Dock', self)
        self.dockAction.setShortcut("Ctrl+D")
        self.dockAction.setToolTip('Toggle dock visibility')
        self.dockAction.setStatusTip('Toggle dock visibility')
        self.dockAction.triggered.connect(self.toggleDockView)

        self.zoomAction = QAction('&Zoom...', self)
        self.zoomAction.setShortcut('Alt+Shift+Z')
        self.zoomAction.setToolTip('Edit zoom factor')
        self.zoomAction.setStatusTip('Edit zoom factor')
        self.zoomAction.triggered.connect(self.editZoomAct)

        self.viewMenu = self.mainMenu.addMenu('&View')
        self.viewMenu.addAction(self.dockAction)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.zoomAction)
        self.viewMenu.aboutToShow.connect(self.updateViewMenu)

        # Window Menu
        self.mainWindowAction = QAction('&Main Window', self)
        self.mainWindowAction.setShortcut('Alt+W')
        self.mainWindowAction.setCheckable(True)
        self.mainWindowAction.setToolTip('Bring main window to front')
        self.mainWindowAction.setStatusTip('Bring main window to front')
        self.mainWindowAction.triggered.connect(self.showMainWindow)

        self.colorDialogAction = QAction('Color &Options', self)
        self.colorDialogAction.setCheckable(True)
        self.colorDialogAction.setToolTip('Bring Color Dialog to front')
        self.colorDialogAction.setStatusTip('Bring Color Dialog to front')
        self.colorDialogAction.triggered.connect(self.showColorDialog)

        self.windowMenu = self.mainMenu.addMenu('&Window')
        self.windowMenu.addAction(self.mainWindowAction)
        self.windowMenu.addAction(self.colorDialogAction)
        self.windowMenu.aboutToShow.connect(self.updateWindowMenu)

    def updateEditMenu(self):
        changed = self.model.currentView != self.model.defaultView
        self.restoreAction.setDisabled(not changed)

        self.maskingAction.setChecked(self.model.currentView.masking)
        self.highlightingAct.setChecked(self.model.currentView.highlighting)

        num_previous_views = len(self.model.previousViews)
        self.undoAction.setText('&Undo ({})'.format(num_previous_views))
        num_subsequent_views = len(self.model.subsequentViews)
        self.redoAction.setText('&Redo ({})'.format(num_subsequent_views))

    def updateBasisMenu(self):
        self.xyAction.setChecked(self.model.currentView.basis == 'xy')
        self.xzAction.setChecked(self.model.currentView.basis == 'xz')
        self.yzAction.setChecked(self.model.currentView.basis == 'yz')

    def updateColorbyMenu(self):
        cv = self.model.currentView
        self.cellAction.setChecked(cv.colorby == 'cell')
        self.materialAction.setChecked(cv.colorby == 'material')
        self.temperatureAction.setChecked(cv.colorby == 'temperature')
        self.densityAction.setChecked(cv.colorby == 'density')

    def updateViewMenu(self):
        if self.dock.isVisible():
            self.dockAction.setText('Hide &Dock')
        else:
            self.dockAction.setText('Show &Dock')

    def updateWindowMenu(self):
        self.colorDialogAction.setChecked(self.colorDialog.isActiveWindow())
        self.mainWindowAction.setChecked(self.isActiveWindow())

    # Menu and shared methods:

    def saveImage(self):
        filename, ext = QFileDialog.getSaveFileName(self,
                                                    "Save Plot Image",
                                                    "untitled",
                                                    "Images (*.png)")
        if filename:
            if "." not in filename:
                filename += ".png"
            self.plotIm.figure.savefig(filename, transparent=True)
            self.statusBar().showMessage('Plot Image Saved', 5000)

    def saveView(self):
        filename, ext = QFileDialog.getSaveFileName(self,
                                                    "Save View Settings",
                                                    "untitled",
                                                    "View Settings (*.pltvw)")
        if filename:
            if "." not in filename:
                filename += ".pltvw"

            saved = {'version': self.model.version,
                     'current': self.model.currentView}
            with open(filename, 'wb') as file:
                pickle.dump(saved, file)

    def openView(self):
        filename, ext = QFileDialog.getOpenFileName(self, "Open View Settings",
                                                    ".", "*.pltvw")
        if filename:
            try:
                with open(filename, 'rb') as file:
                    saved = pickle.load(file)
            except Exception:
                message = 'Error loading plot settings'
                saved = {'version': None,
                         'current': None}
            if saved['version'] == self.model.version:
                self.model.activeView = saved['current']
                self.dock.updateDock()
                self.colorDialog.updateDialogValues()
                self.applyChanges()
                message = '{} settings loaded'.format(filename)
            else:
                message = 'Error loading plot settings. Incompatible model.'
            self.statusBar().showMessage(message, 5000)

    def applyChanges(self):
        if self.model.activeView != self.model.currentView:
            self.statusBar().showMessage('Generating Plot...')
            QApplication.processEvents()

            self.model.storeCurrent()
            self.model.subsequentViews = []
            self.model.generatePlot()
            self.resetModels()
            self.showCurrentView()

        else:
            self.statusBar().showMessage('No changes to apply.', 3000)

    def undo(self):
        self.statusBar().showMessage('Generating Plot...')
        QApplication.processEvents()

        self.model.undo()
        self.resetModels()
        self.showCurrentView()
        self.dock.updateDock()
        self.colorDialog.updateDialogValues()

        if not self.model.previousViews:
            self.undoAction.setDisabled(True)
        self.redoAction.setDisabled(False)

    def redo(self):
        self.statusBar().showMessage('Generating Plot...')
        QApplication.processEvents()

        self.model.redo()
        self.resetModels()
        self.showCurrentView()
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
            self.resetModels()
            self.showCurrentView()
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

    def editColorMap(self, colormap_name, property_type, apply=False):
        self.model.activeView.colormaps[property_type] = colormap_name
        self.plotIm.updateColorMap(colormap_name, property_type)
        self.colorDialog.updateColorMaps()
        if apply:
            self.applyChanges()

    def editColorbarMin(self, min_val, property_type, apply=False):
        av = self.model.activeView
        current = av.user_minmax[property_type]
        av.user_minmax[property_type] = (min_val, current[1])
        self.colorDialog.updateColorMinMax()
        self.plotIm.updateColorMinMax(property_type)
        if apply:
            self.applyChanges()

    def editColorbarMax(self, max_val, property_type, apply=False):
        av = self.model.activeView
        current = av.user_minmax[property_type]
        av.user_minmax[property_type] = (current[0], max_val)
        self.colorDialog.updateColorMinMax()
        self.plotIm.updateColorMinMax(property_type)
        if apply:
            self.applyChanges()

    def toggleColorbarScale(self, state, property, apply=False):
        av = self.model.activeView
        av.color_scale_log[property] = bool(state)
        # temporary, should be resolved diferently in the future
        cv = self.model.currentView
        cv.color_scale_log[property] = bool(state)
        self.plotIm.updateColorbarScale()
        if apply:
            self.applyChanges()

    def toggleUserMinMax(self, state, property):
        av = self.model.activeView
        av.use_custom_minmax[property] = bool(state)
        if av.user_minmax[property] == (0.0, 0.0):
            av.user_minmax[property] = copy.copy(av.data_minmax[property])
        self.plotIm.updateColorMinMax('temperature')
        self.plotIm.updateColorMinMax('density')
        self.colorDialog.updateColorMinMax()

    def toggleDataIndicatorCheckBox(self, state, property, apply=False):
        av = self.model.activeView
        av.data_indicator_enabled[property] = bool(state)

        cv = self.model.currentView
        cv.data_indicator_enabled[property] = bool(state)

        self.plotIm.updateDataIndicatorVisibility()
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
        if self.dock.isVisible():
            self.dock.hide()
            if not self.isMaximized() and not self.dock.isFloating():
                self.resize(self.width() - self.dock.width(), self.height())
        else:
            self.dock.setVisible(True)
            if not self.isMaximized() and not self.dock.isFloating():
                self.resize(self.width() + self.dock.width(), self.height())
        self.resizePixmap()
        self.showMainWindow()

    def editZoomAct(self):
        percent, ok = QInputDialog.getInt(self, "Edit Zoom", "Zoom Percent:",
                                          self.dock.zoomBox.value(), 25, 2000)
        if ok:
            self.dock.zoomBox.setValue(percent)

    def editZoom(self, value):
        self.zoom = value
        self.resizePixmap()
        self.dock.zoomBox.setValue(value)

    def showMainWindow(self):
        self.raise_()
        self.activateWindow()

    def showColorDialog(self):
        self.colorDialog.show()
        self.colorDialog.raise_()
        self.colorDialog.activateWindow()

    # Dock methods:

    def editSingleOrigin(self, value, dimension):
        self.model.activeView.origin[dimension] = value

    def editPlotAlpha(self, value):
        self.model.activeView.plotAlpha = value
        self.dock.updatePlotAlpha()

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
        self.model.activeView.v_res = value
        self.dock.updateVRes()

    def editHRes(self, value):
        self.model.activeView.h_res = value
        self.onRatioChange()
        self.dock.updateHRes()

    # Color dialog methods:

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

    # Plot image methods

    def editPlotOrigin(self, xOr, yOr, zOr=None, apply=False):
        if zOr is not None:
            self.model.activeView.origin = [xOr, yOr, zOr]
        else:
            origin = [None, None, None]
            origin[self.xBasis] = xOr
            origin[self.yBasis] = yOr
            origin[self.zBasis] = self.model.activeView.origin[self.zBasis]
            self.model.activeView.origin = origin

        self.dock.updateOrigin()

        if apply:
            self.applyChanges()

    def revertDockControls(self):
        self.dock.revertToCurrent()

    def editDomainColor(self, kind, id):
        if kind == 'Cell':
            domain = self.model.activeView.cells
        else:
            domain = self.model.activeView.materials

        current_color = domain[id].color
        dlg = QColorDialog(self)

        if isinstance(current_color, tuple):
            dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        elif isinstance(current_color, str):
            current_color = openmc.plots._SVG_COLORS[current_color]
            dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec_():
            new_color = dlg.currentColor().getRgb()[:3]
            domain[id].color = new_color

        self.applyChanges()

    def toggleDomainMask(self, state, kind, id):
        if kind == 'Cell':
            domain = self.model.activeView.cells
        else:
            domain = self.model.activeView.materials

        domain[id].masked = bool(state)
        self.applyChanges()

    def toggleDomainHighlight(self, state, kind, id):
        if kind == 'Cell':
            domain = self.model.activeView.cells
        else:
            domain = self.model.activeView.materials

        domain[id].highlighted = bool(state)
        self.applyChanges()

    # Helper methods:

    def restoreWindowSettings(self):
        settings = QtCore.QSettings()

        self.resize(settings.value("mainWindow/Size",
                                   QtCore.QSize(800, 600)))
        self.move(settings.value("mainWindow/Position",
                                 QtCore.QPoint(100, 100)))
        self.restoreState(settings.value("mainWindow/State"))

        self.colorDialog.resize(settings.value("colorDialog/Size",
                                               QtCore.QSize(400, 500)))
        self.colorDialog.move(settings.value("colorDialog/Position",
                                             QtCore.QPoint(600, 200)))
        is_visible = settings.value("colorDialog/Visible", 0)
        is_visible = bool(int(is_visible))
        self.colorDialog.setVisible(is_visible)

    def restoreModelSettings(self):
        if os.path.isfile("plot_settings.pkl"):

            with open('plot_settings.pkl', 'rb') as file:
                model = pickle.load(file)

            if model.defaultView == self.model.defaultView:
                self.model.currentView = model.currentView
                self.model.activeView = copy.deepcopy(model.currentView)
                self.model.previousViews = model.previousViews
                self.model.subsequentViews = model.subsequentViews
                if os.path.isfile('plot_ids.binary') \
                   and os.path.isfile('plot.ppm'):
                    self.restored = True

    def resetModels(self):
        self.cellsModel = DomainTableModel(self.model.activeView.cells)
        self.materialsModel = DomainTableModel(self.model.activeView.materials)
        self.cellsModel.beginResetModel()
        self.cellsModel.endResetModel()
        self.materialsModel.beginResetModel()
        self.materialsModel.endResetModel()
        self.colorDialog.updateDomainTabs()

    def showCurrentView(self):
        self.resizePixmap()
        self.updateScale()
        self.updateRelativeBases()

        if self.model.previousViews:
            self.undoAction.setDisabled(False)
        if self.model.subsequentViews:
            self.redoAction.setDisabled(False)
        else:
            self.redoAction.setDisabled(True)

        self.statusBar().showMessage('Done', 1000)
        self.adjustWindow()

    def updateScale(self):
        cv = self.model.currentView
        self.scale = (cv.h_res / cv.width,
                      cv.v_res / cv.height)

    def updateRelativeBases(self):
        cv = self.model.currentView
        self.xBasis = 0 if cv.basis[0] == 'x' else 1
        self.yBasis = 1 if cv.basis[1] == 'y' else 2
        self.zBasis = 3 - (self.xBasis + self.yBasis)

    def adjustWindow(self):
        self.screen = app.desktop().screenGeometry()
        self.setMaximumSize(self.screen.width(), self.screen.height())

    def onRatioChange(self):
        av = self.model.activeView
        if av.aspectLock:
            ratio = av.width / max(av.height, .001)
            av.v_res = int(av.h_res / ratio)
            self.dock.updateVRes()

    def showCoords(self, xPlotPos, yPlotPos):
        cv = self.model.currentView
        if cv.basis == 'xy':
            coords = ("({}, {}, {})".format(round(xPlotPos, 2),
                                            round(yPlotPos, 2),
                                            round(cv.origin[2], 2)))
        elif cv.basis == 'xz':
            coords = ("({}, {}, {})".format(round(xPlotPos, 2),
                                            round(cv.origin[1], 2),
                                            round(yPlotPos, 2)))
        else:
            coords = ("({}, {}, {})".format(round(cv.origin[0], 2),
                                            round(xPlotPos, 2),
                                            round(yPlotPos, 2)))
        self.coord_label.setText('{}'.format(coords))

    def resizePixmap(self):
        z = self.zoom / 100.
        self.plotIm.setPixmap(self.frame.width() * z,
                              self.frame.height() * z)
        self.plotIm.adjustSize()

    def moveEvent(self, event):
        self.adjustWindow()

    def resizeEvent(self, event):
        z = self.zoom / 101.
        self.plotIm.resize(self.frame.width() * z,
                           self.frame.height() * z)
        self.updateScale()
        # if hasattr(self.model, 'image') and self.model.image is not None:
        #     self.adjustWindow()
        #     self.updateScale()

    def closeEvent(self, event):
        settings = QtCore.QSettings()
        settings.setValue("mainWindow/Size", self.size())
        settings.setValue("mainWindow/Position", self.pos())
        settings.setValue("mainWindow/State", self.saveState())

        settings.setValue("colorDialog/Size", self.colorDialog.size())
        settings.setValue("colorDialog/Position", self.colorDialog.pos())
        visible = int(self.colorDialog.isVisible())
        settings.setValue("colorDialog/Visible", visible)

        if len(self.model.previousViews) > 10:
            self.model.previousViews = self.model.previousViews[-10:]
        if len(self.model.subsequentViews) > 10:
            self.model.subsequentViews = self.model.subsequentViews[-10:]

        with open('plot_settings.pkl', 'wb') as file:
            pickle.dump(self.model, file)

if __name__ == '__main__':

    path_icon = str(Path(__file__).parent / 'assets/openmc_logo.png')
    path_splash = str(Path(__file__).parent / 'assets/splash.png')

    app = QApplication(sys.argv)
    app.setOrganizationName("OpenMC")
    app.setOrganizationDomain("openmc.org")
    app.setApplicationName("OpenMC Plot Explorer")
    app.setWindowIcon(QtGui.QIcon(path_icon))
    app.setAttribute(QtCore.Qt.AA_DontShowIconsInMenus, True)

    splash_pix = QtGui.QPixmap(path_splash)
    print(splash_pix)
    splash = QSplashScreen(splash_pix, QtCore.Qt.WindowStaysOnTopHint)
    splash.setMask(splash_pix.mask())
    splash.show()
    app.processEvents()
    splash.setMask(splash_pix.mask())
    splash.showMessage("Loading Model...",
                       QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom)
    app.processEvents()
    # load OpenMC model on another thread
    loader_thread = Thread(target=openmc.capi.init, args=(['-c'],))
    loader_thread.start()
    # while thread is working, process app events
    while loader_thread.is_alive():
        app.processEvents()

    splash.clearMessage()
    splash.showMessage("Starting GUI...",
                       QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom)
    app.processEvents()

    FM = QtGui.QFontMetricsF(app.font())
    mainWindow = MainWindow()
    # connect splashscreen to main window, close when main window opens
    mainWindow.loadGui()
    mainWindow.show()
    splash.close()
    sys.exit(app.exec_())
