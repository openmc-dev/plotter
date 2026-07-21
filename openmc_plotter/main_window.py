import copy
from functools import partial
from pathlib import Path
import pickle
from threading import Thread

from PySide6 import QtCore, QtGui
from PySide6.QtGui import QKeyEvent, QAction
from PySide6.QtWidgets import (QApplication, QLabel, QSizePolicy, QMainWindow,
                               QScrollArea, QMessageBox, QFileDialog,
                               QColorDialog, QInputDialog, QWidget, QDialog,
                               QVBoxLayout, QPlainTextEdit, QDialogButtonBox,
                               QGestureEvent)

import openmc
import openmc.lib

try:
    import vtk
    _HAVE_VTK = True
except ImportError:
    _HAVE_VTK = False

from .plotmodel import PlotModel, DomainTableModel, hash_model
from .plotgui import PlotImage, ColorDialog
from .docks import TabbedDock
from .overlays import ShortcutsOverlay
from .tools import ExportDataDialog, SourceSitesDialog


def _openmcReload(threads=None, model_path='.'):
    # reset OpenMC memory, instances
    openmc.lib.reset()
    openmc.lib.finalize()
    # initialize geometry (for volume calculation)
    openmc.lib.settings.output_summary = False
    args = ["-c"]
    if threads is not None:
        args += ["-s", str(threads)]
    args.append(str(model_path))
    openmc.lib.init(args)
    openmc.lib.settings.verbosity = 1


class MainWindow(QMainWindow):
    def __init__(self,
                 font=QtGui.QFontMetrics(QtGui.QFont()),
                 screen_size=QtCore.QSize(),
                 model_path='.',
                 threads=None,
                 resolution=None):
        super().__init__()

        self.screen = screen_size
        self.font_metric = font
        self.setWindowTitle('OpenMC Plot Explorer')
        self.model_path = Path(model_path)
        self.threads = threads
        self.default_res = resolution
        self.model = None
        self.plot_manager = None
        self.materialPropsDialog = None
        self.materialPropsText = None

    def loadGui(self, use_settings_pkl=True):

        self.pixmap = None
        self.zoom = 100

        self.loadModel(use_settings_pkl=use_settings_pkl)

        # Create viewing area
        self.frame = QScrollArea(self)
        cw = QWidget()
        self.frame.setCornerWidget(cw)
        self.frame.setAlignment(QtCore.Qt.AlignCenter)
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCentralWidget(self.frame)

        # connect pinch gesture (OSX)
        self.grabGesture(QtCore.Qt.PinchGesture)

        # Create plot image
        self.plotIm = PlotImage(self.model, self.frame, self)
        self.plotIm.frozen = True
        self.frame.setWidget(self.plotIm)

        # Tabbed Dock (contains Geometry, Tallies, and Meshes)
        self.dock = TabbedDock(self.model, self.font_metric, self)
        self.dock.setObjectName("Options Dock")
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dock)

        # Create shortcuts for accessing panels
        self.geometryPanel = self.dock.geometryPanel
        self.tallyPanel = self.dock.tallyPanel
        self.meshAnnotationPanel = self.dock.meshAnnotationPanel

        # Color Dialog
        self.colorDialog = ColorDialog(self.model, self.font_metric, self)
        self.colorDialog.hide()

        # Tools
        self.exportDataDialog = ExportDataDialog(self.model, self.font_metric, self)
        self.sourceSitesDialog = SourceSitesDialog(self.model, self.font_metric, self)

        # Keyboard overlay
        self.shortcutOverlay = ShortcutsOverlay(self)
        self.shortcutOverlay.hide()

        # Restore Window Settings
        self.restoreWindowSettings()

        # Create menubar
        self.createMenuBar()
        self.updateEditMenu()

        # Status Bar
        self.coord_label = QLabel()
        self.statusBar().addPermanentWidget(self.coord_label)
        self.coord_label.hide()

        self.plot_manager = self.model.plot_manager
        self.plot_manager.plot_started.connect(self._on_plot_started)
        self.plot_manager.plot_queued.connect(self._on_plot_queued)
        self.plot_manager.plot_finished.connect(self._on_plot_finished)
        self.plot_manager.plot_error.connect(self._on_plot_error)
        self.plot_manager.plot_idle.connect(self._on_plot_idle)

        # Load Plot
        self.geometryPanel.update()
        self.tallyPanel.update()
        self.colorDialog.updateDialogValues()

        QtCore.QTimer.singleShot(0, self.requestPlotUpdate)

        self.plotIm.frozen = False

    def event(self, event):
        # use pinch event to update zoom
        if isinstance(event, QGestureEvent):
            pinch = event.gesture(QtCore.Qt.PinchGesture)
            self.editZoom(self.zoom * pinch.scaleFactor())
        if isinstance(event, QKeyEvent) and hasattr(self, "shortcutOverlay"):
            self.shortcutOverlay.event(event)
        return super().event(event)

    def show(self):
        super().show()
        self.plotIm._resize()

    def toggleShortcuts(self):
        if self.shortcutOverlay.isVisible():
            self.shortcutOverlay.close()
        else:
            self.shortcutOverlay.move(0, 0)
            self.shortcutOverlay.resize(self.width(), self.height())
            self.shortcutOverlay.show()

    # Create and update menus:
    def createMenuBar(self):
        self.mainMenu = self.menuBar()

        # File Menu
        self.reloadModelAction = QAction("&Reload model...", self)
        self.reloadModelAction.setShortcut("Ctrl+Shift+R")
        self.reloadModelAction.setToolTip("Reload current model")
        self.reloadModelAction.setStatusTip("Reload current model")
        reload_connector = partial(self.loadModel, reload=True)
        self.reloadModelAction.triggered.connect(reload_connector)

        self.saveImageAction = QAction("&Save Image As...", self)
        self.saveImageAction.setShortcut("Ctrl+Shift+S")
        self.saveImageAction.setToolTip('Save plot image')
        self.saveImageAction.setStatusTip('Save plot image')
        save_image_connector = partial(self.saveImage, filename=None)
        self.saveImageAction.triggered.connect(save_image_connector)

        self.copyImageAction = QAction("&Copy Image", self)
        self.copyImageAction.setShortcut("Ctrl+Shift+C")
        self.copyImageAction.setToolTip('Copy plot image to clipboard')
        self.copyImageAction.setStatusTip('Copy plot image to clipboard')
        self.copyImageAction.triggered.connect(self.copyImageToClipboard)

        self.saveViewAction = QAction("Save &View...", self)
        self.saveViewAction.setShortcut(QtGui.QKeySequence.Save)
        self.saveViewAction.setStatusTip('Save current view settings')
        self.saveViewAction.triggered.connect(self.saveView)

        self.openAction = QAction("&Open View...", self)
        self.openAction.setShortcut(QtGui.QKeySequence.Open)
        self.openAction.setToolTip('Open saved view settings')
        self.openAction.setStatusTip('Open saved view settings')
        self.openAction.triggered.connect(self.openView)

        self.quitAction = QAction("&Quit", self)
        self.quitAction.setShortcut(QtGui.QKeySequence.Quit)
        self.quitAction.setToolTip('Quit OpenMC Plot Explorer')
        self.quitAction.setStatusTip('Quit OpenMC Plot Explorer')
        self.quitAction.triggered.connect(self.close)

        self.exportDataAction = QAction('E&xport...', self)
        self.exportDataAction.setToolTip('Export model and tally data VTK')
        self.setStatusTip('Export current model and tally data to VTK')
        self.exportDataAction.triggered.connect(self.exportTallyData)
        if not _HAVE_VTK:
            self.exportDataAction.setEnabled(False)
            self.exportDataAction.setToolTip("Disabled: VTK Python module is not installed")

        self.fileMenu = self.mainMenu.addMenu('&File')
        self.fileMenu.addAction(self.reloadModelAction)
        self.fileMenu.addAction(self.copyImageAction)
        self.fileMenu.addAction(self.saveImageAction)
        self.fileMenu.addAction(self.exportDataAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.saveViewAction)
        self.fileMenu.addAction(self.openAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.quitAction)

        # Data Menu
        self.openStatePointAction = QAction("&Open statepoint...", self)
        self.openStatePointAction.setToolTip('Open statepoint file')
        self.openStatePointAction.triggered.connect(self.openStatePoint)

        self.sourceSitesAction = QAction('&Sample source sites...', self)
        self.sourceSitesAction.setToolTip('Add source sites to plot')
        self.setStatusTip('Sample and add source sites to the plot')
        self.sourceSitesAction.triggered.connect(self.plotSourceSites)

        self.importPropertiesAction = QAction("&Import properties...", self)
        self.importPropertiesAction.setToolTip("Import properties")
        self.importPropertiesAction.triggered.connect(self.importProperties)

        self.dataMenu = self.mainMenu.addMenu('D&ata')
        self.dataMenu.addAction(self.openStatePointAction)
        self.dataMenu.addAction(self.sourceSitesAction)
        self.dataMenu.addAction(self.importPropertiesAction)
        self.updateDataMenu()

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

        # Edit -> Other Options
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

        self.overlapAct = QAction('Enable Overlap Coloring', self)
        self.overlapAct.setShortcut('Ctrl+P')
        self.overlapAct.setCheckable(True)
        self.overlapAct.setToolTip('Toggle overlapping regions')
        self.overlapAct.setStatusTip('Toggle display of overlapping '
                                     'regions when enabled')
        overlap_connector = partial(self.toggleOverlaps, apply=True)
        self.overlapAct.toggled.connect(overlap_connector)
        self.editMenu.addAction(self.overlapAct)

        self.undefinedAct = QAction('Enable Undefined Region Coloring', self)
        self.undefinedAct.setShortcut('Ctrl+I')
        self.undefinedAct.setCheckable(True)
        self.undefinedAct.setToolTip('Toggle undefined regions')
        self.undefinedAct.setStatusTip('Toggle display of undefined '
                                       '(not found) regions when enabled')
        undefined_connector = partial(self.toggleUndefined, apply=True)
        self.undefinedAct.toggled.connect(undefined_connector)
        self.editMenu.addAction(self.undefinedAct)

        self.outlineAct = QAction('Enable Domain Outlines', self)
        self.outlineAct.setShortcut('Ctrl+U')
        self.outlineAct.setCheckable(True)
        self.outlineAct.setToolTip('Display Cell/Material Boundaries')
        self.outlineAct.setStatusTip('Toggle display of domain '
                                     'outlines when enabled')
        outline_connector = partial(self.toggleOutlinesCell, apply=True)
        self.outlineAct.toggled.connect(outline_connector)
        self.editMenu.addAction(self.outlineAct)

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
        self.mainWindowAction.setCheckable(True)
        self.mainWindowAction.setToolTip('Bring main window to front')
        self.mainWindowAction.setStatusTip('Bring main window to front')
        self.mainWindowAction.triggered.connect(self.showMainWindow)

        self.colorDialogAction = QAction('Color &Options', self)
        self.colorDialogAction.setCheckable(True)
        self.colorDialogAction.setToolTip('Bring Color Dialog to front')
        self.colorDialogAction.setStatusTip('Bring Color Dialog to front')
        self.colorDialogAction.triggered.connect(self.showColorDialog)

        # Keyboard Shortcuts Overlay
        self.keyboardShortcutsAction = QAction("&Keyboard Shortcuts...", self)
        self.keyboardShortcutsAction.setShortcut("?")
        self.keyboardShortcutsAction.setToolTip("Display Keyboard Shortcuts")
        self.keyboardShortcutsAction.setStatusTip("Display Keyboard Shortcuts")
        self.keyboardShortcutsAction.triggered.connect(self.toggleShortcuts)

        self.windowMenu = self.mainMenu.addMenu('&Window')
        self.windowMenu.addAction(self.mainWindowAction)
        self.windowMenu.addAction(self.colorDialogAction)
        self.windowMenu.addAction(self.keyboardShortcutsAction)
        self.windowMenu.aboutToShow.connect(self.updateWindowMenu)

    def updateEditMenu(self):
        changed = self.model.currentView != self.model.defaultView
        self.restoreAction.setDisabled(not changed)

        toggle_actions = (self.maskingAction, self.highlightingAct,
                          self.outlineAct, self.overlapAct, self.undefinedAct)
        # Temporarily block signals to avoid triggering plot update
        for action in toggle_actions:
            action.blockSignals(True)
        self.maskingAction.setChecked(self.model.currentView.masking)
        self.highlightingAct.setChecked(self.model.currentView.highlighting)
        self.outlineAct.setChecked(self.model.currentView.outlinesCell)
        self.overlapAct.setChecked(self.model.currentView.color_overlaps)
        self.undefinedAct.setChecked(self.model.currentView.color_undefined)
        for action in toggle_actions:
            action.blockSignals(False)

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

    def saveBatchImage(self, view_file):
        """
        Loads a view in the GUI and generates an image

        Parameters
        ----------
        view_file : str or pathlib.Path
            The path to a view file that is compatible with the loaded model.
        """
        # store the
        cv = self.model.currentView
        # load the view from file
        self.loadViewFile(view_file)
        self.waitForPlotIdle()
        self.plotIm.saveImage(view_file.replace('.pltvw', ''))

    # Menu and shared methods
    def loadModel(self, reload=False, use_settings_pkl=True):
        if reload:
            if self.plot_manager is not None:
                self.plot_manager.wait_for_idle()
            self.resetModels()
        else:
            self.model = PlotModel(use_settings_pkl, self.model_path, self.default_res)

            # update plot and model settings
            self.updateRelativeBases()

        self.cellsModel = DomainTableModel(self.model.activeView.cells)
        self.materialsModel = DomainTableModel(self.model.activeView.materials)

        openmc_args = {'threads': self.threads, 'model_path': self.model_path}

        if reload:
            loader_thread = Thread(target=_openmcReload, kwargs=openmc_args)
            loader_thread.start()
            while loader_thread.is_alive():
                self.statusBar().showMessage("Reloading model...")
                QApplication.processEvents()

            self.plotIm.model = self.model
            self.applyChanges()

    def saveImage(self, filename=None):
        if filename is None:
            filename, ext = QFileDialog.getSaveFileName(self,
                                                        "Save Plot Image",
                                                        "untitled",
                                                        "Images (*.png)")
        if filename:
            self.plotIm.saveImage(filename)
            self.statusBar().showMessage('Plot Image Saved', 5000)

    def copyImageToClipboard(self):
        if self.plotIm.copyImageToClipboard():
            self.statusBar().showMessage('Plot Image Copied', 5000)
            return True

        self.statusBar().showMessage('No Plot Image Available', 5000)
        return False

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

    def loadViewFile(self, filename):
        try:
            with open(filename, 'rb') as file:
                saved = pickle.load(file)
        except Exception:
            message = 'Error loading plot settings'
            saved = {'version': None,
                     'current': None}

        if saved['version'] == self.model.version:
            self.model.activeView = saved['current']
            # Handle backward compatibility for outline attributes
            if not hasattr(self.model.activeView, 'outlinesCell'):
                self.model.activeView.outlinesCell = False
            if not hasattr(self.model.activeView, 'outlinesMat'):
                self.model.activeView.outlinesMat = False
            self.geometryPanel.update()
            self.colorDialog.updateDialogValues()
            self.applyChanges()
            message = '{} loaded'.format(filename)
        else:
            message = 'Error loading plot settings. Incompatible model.'
        self.statusBar().showMessage(message, 5000)

    def openView(self):
        filename, ext = QFileDialog.getOpenFileName(self, "Open View Settings",
                                                    ".", "*.pltvw")
        if filename:
            self.loadViewFile(filename)

    def openStatePoint(self):
        # confirm replacement when a statepoint is already open
        if self.model.statepoint:
            msg_box = QMessageBox(self)
            msg_box.setText("A statepoint file is currently open. Continue to "
                            "close it and open a new one?")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
            msg_box.setDefaultButton(QMessageBox.Cancel)
            msg_box.button(QMessageBox.Yes).setText("Continue")
            if msg_box.exec() != QMessageBox.Yes:
                return
            self.closeStatePoint()
        filename, ext = QFileDialog.getOpenFileName(self, "Open StatePoint",
                                                    ".", "*.h5")
        if filename:
            try:
                self.model.openStatePoint(filename)
                message = f'Opened statepoint file: {filename}'
            except Exception as e:
                message = f'Error opening statepoint file: {filename}'
                msg_box = QMessageBox()
                msg = f"Could not open statepoint file:\n{filename}\n\n{e}"
                msg_box.setText(msg)
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.exec()
            finally:
                self.statusBar().showMessage(message, 5000)
            self.updateDataMenu()
            self.tallyPanel.update()

    def importProperties(self):
        filename, ext = QFileDialog.getOpenFileName(self, "Import properties",
                                                    ".", "*.h5")
        if not filename:
            return

        try:
            openmc.lib.import_properties(filename)
            message = 'Imported properties: {}'
        except (FileNotFoundError, OSError, openmc.lib.exc.OpenMCError) as e:
            message = 'Error opening properties file: {}'
            msg_box = QMessageBox()
            msg_box.setText(f"Error opening properties file: \n\n {e} \n")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec()
        finally:
            self.statusBar().showMessage(message.format(filename), 5000)

        if self.model.activeView.colorby == 'temperature':
            self.applyChanges()

    def closeStatePoint(self):
        # remove the statepoint object and update the data menu
        filename = self.model.statepoint.filename
        self.model.statepoint.close()
        self.model.statepoint = None
        self.model.currentView.selectedTally = None
        self.model.activeView.selectedTally = None

        msg = "Closed statepoint file {}".format(filename)
        self.statusBar().showMessage(msg)
        self.updateDataMenu()
        self.tallyPanel.selectTally()
        self.tallyPanel.update()
        self.plotIm.updatePixmap()

    def updateDataMenu(self):
        if self.model.statepoint:
            self.closeStatePointAction = QAction("&Close statepoint", self)
            self.closeStatePointAction.setToolTip("Close current statepoint")
            self.closeStatePointAction.triggered.connect(self.closeStatePoint)
            self.dataMenu.addAction(self.closeStatePointAction)
        elif hasattr(self, "closeStatePointAction"):
            self.dataMenu.removeAction(self.closeStatePointAction)


    def updateMeshAnnotations(self):
        self.model.activeView.mesh_annotations = self.meshAnnotationPanel.get_checked_meshes()

    def plotSourceSites(self):
        self.sourceSitesDialog.show()
        self.sourceSitesDialog.raise_()
        self.sourceSitesDialog.activateWindow()

    def applyChanges(self):
        if self.model.activeView != self.model.currentView:
            if self.model.activeView.selectedTally is not None:
                self.tallyPanel.updateModel()
            self.updateMeshAnnotations()
            self.model.storeCurrent()
            self.model.subsequentViews = []
            self.requestPlotUpdate()
        else:
            self.statusBar().showMessage('No changes to apply.', 3000)

    def undo(self):
        if not self.model.previousViews:
            return
        self.model.undo()
        self.geometryPanel.update()
        self.colorDialog.updateDialogValues()
        self.requestPlotUpdate()

        if not self.model.previousViews:
            self.undoAction.setDisabled(True)
        self.redoAction.setDisabled(False)

    def redo(self):
        if not self.model.subsequentViews:
            return
        self.model.redo()
        self.geometryPanel.update()
        self.colorDialog.updateDialogValues()
        self.requestPlotUpdate()

        if not self.model.subsequentViews:
            self.redoAction.setDisabled(True)
        self.undoAction.setDisabled(False)

    def restoreDefault(self):
        if self.model.currentView != self.model.defaultView:
            self.model.storeCurrent()
            self.model.activeView.adopt_view_params(self.model.defaultView)
            self.geometryPanel.update()
            self.colorDialog.updateDialogValues()
            self.requestPlotUpdate()

            self.model.subsequentViews = []

    def editBasis(self, basis, apply=False):
        self.model.activeView.basis = basis
        self.geometryPanel.updateBasis()
        if apply:
            self.applyChanges()

    def editColorBy(self, domain_kind, apply=False):
        self.model.activeView.colorby = domain_kind
        self.geometryPanel.updateColorBy()
        self.colorDialog.updateColorBy()
        if apply:
            self.applyChanges()

    def editUniverseLevel(self, level, apply=False):
        if level in ('all', ''):
            self.model.activeView.level = -1
        else:
            self.model.activeView.level = int(level)
        self.geometryPanel.updateUniverseLevel()
        self.colorDialog.updateUniverseLevel()
        if apply:
            self.applyChanges()

    def toggleOverlaps(self, state, apply=False):
        self.model.activeView.color_overlaps = bool(state)
        self.colorDialog.updateOverlap()
        if apply:
            self.applyChanges()

    def toggleUndefined(self, state, apply=False):
        self.model.activeView.color_undefined = bool(state)
        self.colorDialog.updateUndefined()
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
                                          self.geometryPanel.zoomBox.value(), 25, 2000)
        if ok:
            self.geometryPanel.zoomBox.setValue(percent)

    def editZoom(self, value):
        self.zoom = value
        self.resizePixmap()
        self.geometryPanel.zoomBox.setValue(value)

    def showMainWindow(self):
        self.raise_()
        self.activateWindow()

    def showColorDialog(self):
        self.colorDialog.show()
        self.colorDialog.raise_()
        self.colorDialog.activateWindow()

    def showExportDialog(self):
        self.exportDataDialog.show()
        self.exportDataDialog.raise_()
        self.exportDataDialog.activateWindow()

    # Dock methods:

    def editSingleOrigin(self, value, dimension):
        self.model.activeView.origin[dimension] = value

    def editPlotAlpha(self, value):
        self.model.activeView.domainAlpha = value

    def editPlotVisibility(self, value):
        self.model.activeView.domainVisible = bool(value)

    def toggleOutlinesCell(self, value, apply=False):
        self.model.activeView.outlinesCell = bool(value)
        self.geometryPanel.updateOutlines()

        if apply:
            self.applyChanges()

    def toggleOutlinesMat(self, value, apply=False):
        self.model.activeView.outlinesMat = bool(value)
        self.geometryPanel.updateOutlines()

        if apply:
            self.applyChanges()

    def editWidth(self, value):
        self.model.activeView.width = value
        self.onRatioChange()
        self.geometryPanel.updateWidth()

    def editHeight(self, value):
        self.model.activeView.height = value
        self.onRatioChange()
        self.geometryPanel.updateHeight()

    def toggleAspectLock(self, state):
        self.model.activeView.aspectLock = bool(state)
        self.onRatioChange()
        self.geometryPanel.updateAspectLock()

    def editVRes(self, value):
        self.model.activeView.v_res = value
        self.geometryPanel.updateVRes()

    def editHRes(self, value):
        self.model.activeView.h_res = value
        self.onRatioChange()
        self.geometryPanel.updateHRes()

    # Color dialog methods:

    def editMaskingColor(self):
        current_color = self.model.activeView.maskBackground
        dlg = QColorDialog(self)

        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activeView.maskBackground = new_color
            self.colorDialog.updateMaskingColor()

    def editHighlightColor(self):
        current_color = self.model.activeView.highlightBackground
        dlg = QColorDialog(self)

        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activeView.highlightBackground = new_color
            self.colorDialog.updateHighlightColor()

    def editAlpha(self, value):
        self.model.activeView.highlightAlpha = value

    def editSeed(self, value):
        self.model.activeView.highlightSeed = value

    def editOverlapColor(self, apply=False):
        current_color = self.model.activeView.overlap_color
        dlg = QColorDialog(self)
        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activeView.overlap_color = new_color
            self.colorDialog.updateOverlapColor()

        if apply:
            self.applyChanges()

    def editUndefinedInternalColor(self, apply=False):
        current_color = self.model.activeView.undefined_internal_color
        dlg = QColorDialog(self)
        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activeView.undefined_internal_color = new_color
            self.colorDialog.updateUndefinedColors()

        if apply:
            self.applyChanges()

    def editUndefinedExternalColor(self, apply=False):
        current_color = self.model.activeView.undefined_external_color
        dlg = QColorDialog(self)
        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activeView.undefined_external_color = new_color
            self.colorDialog.updateUndefinedColors()

        if apply:
            self.applyChanges()

    def editBackgroundColor(self, apply=False):
        current_color = self.model.activeView.domainBackground
        dlg = QColorDialog(self)

        dlg.setCurrentColor(QtGui.QColor.fromRgb(*current_color))
        if dlg.exec():
            new_color = dlg.currentColor().getRgb()[:3]
            self.model.activeView.domainBackground = new_color
            self.colorDialog.updateBackgroundColor()

        if apply:
            self.applyChanges()

    def resetColors(self):
        self.model.resetColors()
        self.colorDialog.updateDialogValues()
        self.applyChanges()

    # Tally dock methods

    def editSelectedTally(self, event):
        av = self.model.activeView

        if event is None or event == "None" or event == "":
            av.selectedTally = None
        else:
            av.selectedTally = int(event.split()[1])
        self.tallyPanel.selectTally(event)

    def editTallyValue(self, event):
        av = self.model.activeView
        av.tallyValue = event

    def toggleTallyVisibility(self, state, apply=False):
        av = self.model.activeView
        av.tallyDataVisible = bool(state)
        if apply:
            self.applyChanges()

    def toggleTallyLogScale(self, state, apply=False):
        av = self.model.activeView
        av.tallyDataLogScale = bool(state)
        if apply:
            self.applyChanges()

    def toggleTallyMaskZero(self, state):
        av = self.model.activeView
        av.tallyMaskZeroValues = bool(state)

    def toggleTallyVolumeNorm(self, state):
        av = self.model.activeView
        av.tallyVolumeNorm = bool(state)

    def editTallyAlpha(self, value, apply=False):
        av = self.model.activeView
        av.tallyDataAlpha = value
        if apply:
            self.applyChanges()

    def toggleTallyContours(self, state):
        av = self.model.activeView
        av.tallyContours = bool(state)

    def editTallyContourLevels(self, value):
        av = self.model.activeView
        av.tallyContourLevels = value

    def toggleTallyDataIndicator(self, state, apply=False):
        av = self.model.activeView
        av.tallyDataIndicator = bool(state)
        if apply:
            self.applyChanges()

    def toggleTallyDataClip(self, state):
        av = self.model.activeView
        av.clipTallyData = bool(state)

    def setTallyMinMaxType(self, index, apply=False):
        """Set the min/max type for tally data.

        Parameters
        ----------
        index : int
            Index of the selected option: 0='full', 1='visible', 2='custom'
        apply : bool
            Whether to apply changes immediately
        """
        av = self.model.activeView
        type_map = {0: 'full', 1: 'visible', 2: 'custom'}
        new_type = type_map.get(index, 'full')
        av.tallyDataMinMaxType = new_type

        # Immediately update visibility of min/max fields based on selection
        show_custom = (new_type == 'custom')
        form = self.tallyPanel.tallyColorForm
        form.minLabel.setVisible(show_custom)
        form.minBox.setVisible(show_custom)
        form.maxLabel.setVisible(show_custom)
        form.maxBox.setVisible(show_custom)

        if apply:
            self.applyChanges()

    def editTallyDataMin(self, value, apply=False):
        av = self.model.activeView
        av.tallyDataMin = value
        if apply:
            self.applyChanges()

    def editTallyDataMax(self, value, apply=False):
        av = self.model.activeView
        av.tallyDataMax = value
        if apply:
            self.applyChanges()

    def editTallyDataColormap(self, cmap, apply=False):
        av = self.model.activeView
        av.tallyDataColormap = cmap
        if apply:
            self.applyChanges()

    def toggleReverseCmap(self, state):
        av = self.model.activeView
        av.tallyDataReverseCmap = bool(state)

    def updateTallyMinMax(self):
        self.tallyPanel.updateMinMax()

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

        self.geometryPanel.updateOrigin()

        if apply:
            self.applyChanges()

    def revertDockControls(self):
        self.geometryPanel.revertToCurrent()

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
        if dlg.exec():
            new_color = dlg.currentColor().getRgb()[:3]
            domain.set_color(id, new_color)

        self.applyChanges()

    def toggleDomainMask(self, state, kind, id):
        if kind == 'Cell':
            domain = self.model.activeView.cells
        else:
            domain = self.model.activeView.materials

        domain.set_masked(id, bool(state))
        self.applyChanges()

    def toggleDomainHighlight(self, state, kind, id):
        if kind == 'Cell':
            domain = self.model.activeView.cells
        else:
            domain = self.model.activeView.materials

        domain.set_highlight(id, bool(state))
        self.applyChanges()

    # Helper methods:

    def restoreWindowSettings(self):
        settings = QtCore.QSettings()

        self.resize(settings.value("mainWindow/Size",
                                   QtCore.QSize(1200, 800)))
        self.move(settings.value("mainWindow/Position",
                                 QtCore.QPoint(100, 100)))
        self.restoreState(settings.value("mainWindow/State"))

        self.colorDialog.resize(settings.value("colorDialog/Size",
                                               QtCore.QSize(400, 500)))
        self.colorDialog.move(settings.value("colorDialog/Position",
                                             QtCore.QPoint(600, 200)))
        is_visible = settings.value("colorDialog/Visible", 0)
        # some versions of PySide will return None rather than the default value
        if is_visible is None:
            is_visible = False
        else:
            is_visible = bool(int(is_visible))

        self.colorDialog.setVisible(is_visible)

    def resetModels(self):
        self.cellsModel = DomainTableModel(self.model.activeView.cells)
        self.materialsModel = DomainTableModel(self.model.activeView.materials)
        self.cellsModel.beginResetModel()
        self.cellsModel.endResetModel()
        self.materialsModel.beginResetModel()
        self.materialsModel.endResetModel()
        self.colorDialog.updateDomainTabs()

    def showCurrentView(self):
        self.updateScale()
        self.updateRelativeBases()
        self.plotIm.updatePixmap()

        if self.model.previousViews:
            self.undoAction.setDisabled(False)
        if self.model.subsequentViews:
            self.redoAction.setDisabled(False)
        else:
            self.redoAction.setDisabled(True)

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
        self.setMaximumSize(self.screen.width(), self.screen.height())

    def onRatioChange(self):
        av = self.model.activeView
        if av.aspectLock:
            ratio = av.width / max(av.height, .001)
            av.v_res = int(av.h_res / ratio)
            self.geometryPanel.updateVRes()

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
        self.plotIm._resize()
        self.plotIm.adjustSize()

    def moveEvent(self, event):
        self.adjustWindow()

    def resizeEvent(self, event):
        self.plotIm._resize()
        self.adjustWindow()
        self.updateScale()
        if self.shortcutOverlay.isVisible():
            self.shortcutOverlay.resize(self.width(), self.height())

    def closeEvent(self, event):
        if self.plot_manager is not None:
            self.plot_manager.wait_for_idle(timeout_ms=250)
            self.plot_manager.shutdown()
        settings = QtCore.QSettings()
        settings.setValue("mainWindow/Size", self.size())
        settings.setValue("mainWindow/Position", self.pos())
        settings.setValue("mainWindow/State", self.saveState())

        settings.setValue("colorDialog/Size", self.colorDialog.size())
        settings.setValue("colorDialog/Position", self.colorDialog.pos())
        visible = int(self.colorDialog.isVisible())
        settings.setValue("colorDialog/Visible", visible)

        openmc.lib.finalize()

        self.saveSettings()

    def requestPlotUpdate(self, view=None):
        if self.model is None:
            return
        if view is None:
            view = self.model.activeView
        view_snapshot = copy.deepcopy(view)
        if self.model.can_reuse_maps(view_snapshot):
            view_params = self.model.view_params_payload(view_snapshot)
            self.plot_manager.set_latest_view_params(view_params)
            self.plot_manager.clear_pending()
            self.model.makePlot(view_snapshot, self.model.geom_data, self.model.property_data)
            self.resetModels()
            self.showCurrentView()
            if not self.plot_manager.is_busy:
                self._on_plot_idle()
            return
        view_params = self.model.view_params_payload(view_snapshot)
        self.plot_manager.enqueue(view_snapshot, view_params)

    def waitForPlotIdle(self, timeout_ms=None):
        if self.plot_manager is not None:
            return self.plot_manager.wait_for_idle(timeout_ms)
        return True

    def _on_plot_started(self):
        self.plotIm.showUpdatingOverlay("Generating Plot...")

    def _on_plot_queued(self):
        self.plotIm.showUpdatingOverlay("Generating Plot... (update queued)")

    def _on_plot_finished(self, view_snapshot, view_params, geom_data, property_data):
        if view_params != self.plot_manager.latest_view_params:
            return
        self.model.makePlot(view_snapshot, geom_data, property_data)
        self.resetModels()
        self.showCurrentView()

    def _on_plot_error(self, error_msg):
        msg_box = QMessageBox()
        msg_box.setText(f"Failed to generate plot:\n\n{error_msg}")
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec()

    def _on_plot_idle(self):
        self.plotIm.hideUpdatingOverlay()

    def saveSettings(self):
        if self.model.statepoint:
            self.model.statepoint.close()

        # get hashes for material.xml and geometry.xml at close
        mat_xml_hash, geom_xml_hash = hash_model(self.model_path)

        pickle_data = {
            'version': self.model.version,
            'currentView': self.model.currentView,
            'statepoint': self.model.statepoint,
            'mat_xml_hash': mat_xml_hash,
            'geom_xml_hash': geom_xml_hash
        }
        if self.model_path.is_file():
            settings_pkl = self.model_path.with_name('plot_settings.pkl')
        else:
            settings_pkl = self.model_path / 'plot_settings.pkl'
        with settings_pkl.open('wb') as file:
            pickle.dump(pickle_data, file)

    def exportTallyData(self):
        # show export tool dialog
        self.showExportDialog()

    def viewMaterialProps(self, id):
        """Display material properties in a scrollable dialog."""
        mat = openmc.lib.materials[id]
        if mat.name:
            title = f"Material {id} ({mat.name}) Properties"
        else:
            title = f"Material {id} Properties"

        msg_str = f"{title}\n\n"

        # get density and temperature
        dens_g = mat.get_density(units='g/cm3')
        dens_a = mat.get_density(units='atom/b-cm')
        msg_str += f"Density: {dens_g:.3f} g/cm3 ({dens_a:.3e} atom/b-cm)\n"
        msg_str += f"Temperature: {mat.temperature} K\n\n"

        # get nuclides and their densities
        msg_str += "Nuclide densities [atom/b-cm]:\n"
        for nuc, dens in zip(mat.nuclides, mat.densities):
            msg_str += f'{nuc}: {dens:5.3e}\n'

        if self.materialPropsDialog is None:
            dialog = QDialog(self)
            dialog.setModal(False)
            dialog.setMinimumSize(560, 420)

            layout = QVBoxLayout(dialog)
            text = QPlainTextEdit(dialog)
            text.setReadOnly(True)
            text.setLineWrapMode(QPlainTextEdit.NoWrap)
            layout.addWidget(text)

            buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=dialog)
            buttons.rejected.connect(dialog.close)
            buttons.accepted.connect(dialog.close)
            layout.addWidget(buttons)

            self.materialPropsDialog = dialog
            self.materialPropsText = text

        self.materialPropsDialog.setWindowTitle(title)
        self.materialPropsText.setPlainText(msg_str)
        self.materialPropsText.moveCursor(QtGui.QTextCursor.Start)
        self.materialPropsDialog.show()
        self.materialPropsDialog.raise_()
        self.materialPropsDialog.activateWindow()
