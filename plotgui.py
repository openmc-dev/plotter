#!/usr/bin/python3
# -*- coding: utf-8 -*-

from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QApplication, QGroupBox, QFormLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QSizePolicy, QSpacerItem, QMainWindow,
    QCheckBox, QRubberBand, QMenu, QAction, QMenuBar, QFileDialog, QDialog,
    QTabWidget, QGridLayout, QToolButton, QColorDialog, QFrame, QDockWidget,
    QTableView, QItemDelegate, QHeaderView, QSlider)
from matplotlib.backends.qt_compat import is_pyqt5
from matplotlib.figure import Figure
from matplotlib import image as mpimage
import matplotlib.pyplot as plt

if is_pyqt5():
    from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
else:
    from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)

from plot_colors import rgb_normalize
from plotmodel import DomainDelegate, _NOT_FOUND, _VOID_REGION

class PlotImage(FigureCanvas):

    def __init__(self, model, parent, main):

        super(FigureCanvas, self).__init__(Figure())

        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)

        FigureCanvas.updateGeometry(self)

        self.model = model
        self.mw = main
        self.parent = parent

        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.band_origin = QtCore.QPoint()
        self.x_plot_origin = None
        self.y_plot_origin = None

        self.menu = QMenu(self)

    def enterEvent(self, event):
        self.setCursor(QtCore.Qt.CrossCursor)
        self.mw.coord_label.show()

    def leaveEvent(self, event):
        self.mw.coord_label.hide()
        self.mw.statusBar().showMessage("")

    def mousePressEvent(self, event):
        self.mw.coord_label.hide()

        # Set rubber band absolute and relative position
        self.band_origin = event.pos()
        self.x_plot_origin, self.y_plot_origin = self.getPlotCoords(event.pos())

        # Create rubber band
        self.rubber_band.setGeometry(QtCore.QRect(self.band_origin, QtCore.QSize()))

        FigureCanvas.mousePressEvent(self, event)

    def getPlotCoords(self, pos):

        cv = self.model.currentView

        # get the normalized axis coordinates from the event display units
        xPlotCoord, yPlotCoord = self.ax.transAxes.inverted().transform((pos.x(), pos.y()))
        # flip the y-axis (its zero is in the upper left)
        yPlotCoord = 1 - yPlotCoord

        # scale axes using the plot extents
        xPlotCoord = self.ax.dataLim.x0 + xPlotCoord * self.ax.dataLim.width
        yPlotCoord = self.ax.dataLim.y0 + yPlotCoord * self.ax.dataLim.height

        # set coordinate label if pointer is in the axes
        if self.parent.underMouse():
            self.mw.coord_label.show()
            self.mw.showCoords(xPlotCoord, yPlotCoord)
        else:
            self.mw.coord_label.hide()

        return (xPlotCoord, yPlotCoord)

    def getIDinfo(self, event):

        cv = self.model.currentView

        # get origin in axes coordinates
        x0, y0 = self.ax.transAxes.transform((0.,0.))

        # get the extents of the axes box in axes coordinates
        bbox = self.ax.get_window_extent().transformed(
            self.figure.dpi_scale_trans.inverted())
        # get dimensions and scale using dpi
        width, height = bbox.width, bbox.height
        width *= self.figure.dpi
        height *= self.figure.dpi

        # use factor to get proper x,y position in pixels
        factor = (width/cv.h_res, height/cv.v_res)
        xPos = int((event.pos().x()-x0 + 0.01) / factor[0])
        yPos = int((event.pos().y()-y0 + 0.01) / factor[1])

        # check that the position is in the axes view
        if  0 <= yPos < self.model.currentView.v_res \
            and 0 <= xPos and xPos < self.model.currentView.h_res:
            id = f"{self.model.ids[yPos][xPos]}"
            temp = f"{self.model.properties[yPos][xPos][0]:g}"
            density = f"{self.model.properties[yPos][xPos][1]:g}"
        else:
            id = str(_NOT_FOUND)
            density = str(_NOT_FOUND)
            temp = str(_NOT_FOUND)

        if self.model.currentView.colorby == 'cell':
            domain = self.model.activeView.cells
            domain_kind = 'Cell'
        else:
            domain = self.model.activeView.materials
            domain_kind = 'Material'

        properties = {'density' : density,
                      'temperature' : temp}

        return id, properties, domain, domain_kind

    def mouseDoubleClickEvent(self, event):

        xCenter, yCenter = self.getPlotCoords(event.pos())
        self.mw.editPlotOrigin(xCenter, yCenter, apply=True)

        FigureCanvas.mouseDoubleClickEvent(self, event)

    def mouseMoveEvent(self, event):

        # Show Cursor position relative to plot in status bar
        xPlotPos, yPlotPos = self.getPlotCoords(event.pos())

        # Show Cell/Material ID, Name in status bar
        id, properties, domain, domain_kind = self.getIDinfo(event)
        if self.ax.contains_point((event.pos().x(), event.pos().y())):

            if id == str(_VOID_REGION):
                domainInfo = ("VOID")
            elif id != str(_NOT_FOUND) and domain[id].name:
                domainInfo = (f"{domain_kind} {id}: \"{domain[id].name}\"\t "
                             f"Density: {properties['density']} g/cm3\t"
                             f"Temperature: {properties['temperature']} K")
            elif id != str(_NOT_FOUND):
                domainInfo = (f"{domain_kind} {id}\t"
                              f"Density: {properties['density']} g/cm3\t"
                              f"Temperature: {properties['temperature']} K")
            else:
                domainInfo = ""
        else:
            domainInfo = ""

        self.mw.statusBar().showMessage(f" {domainInfo}")

        # Update rubber band and values if mouse button held down
        if event.buttons() == QtCore.Qt.LeftButton:
            self.rubber_band.setGeometry(
                QtCore.QRect(self.band_origin, event.pos()).normalized())

            # Show rubber band if both dimensions > 10 pixels
            if self.rubber_band.width() > 10 and self.rubber_band.height() > 10:
                self.rubber_band.show()
            else:
                self.rubber_band.hide()

            # Update plot X Origin
            xCenter = (self.x_plot_origin + xPlotPos) / 2
            yCenter = (self.y_plot_origin + yPlotPos) / 2
            self.mw.editPlotOrigin(xCenter, yCenter)

            modifiers = event.modifiers()

            # Zoom out if Shift held
            if modifiers == QtCore.Qt.ShiftModifier:
                cv = self.model.currentView
                bandwidth = abs(self.band_origin.x() - event.pos().x())
                width = cv.width * (cv.h_res / max(bandwidth, .001))
                bandheight = abs(self.band_origin.y() - event.pos().y())
                height = cv.height * (cv.v_res / max(bandheight, .001))
            else: # Zoom in
                width = max(abs(self.x_plot_origin - xPlotPos), 0.1)
                height = max(abs(self.y_plot_origin - yPlotPos), 0.1)

            self.mw.editWidth(width)
            self.mw.editHeight(height)

    def mouseReleaseEvent(self, event):

        if self.rubber_band.isVisible():
            self.rubber_band.hide()
            self.mw.applyChanges()
        else:
            self.mw.revertDockControls()

    def wheelEvent(self, event):

        if event.delta() and event.modifiers() == QtCore.Qt.ShiftModifier:
            numDegrees = event.delta() / 8

            if 24 < self.mw.zoom + numDegrees < 5001:
                self.mw.editZoom(self.mw.zoom + numDegrees)

    def contextMenuEvent(self, event):

        self.menu.clear()

        self.mw.undoAction.setText(f'&Undo ({len(self.model.previousViews)})')
        self.mw.redoAction.setText(f'&Redo ({len(self.model.subsequentViews)})')

        id, properties, domain, domain_kind = self.getIDinfo(event)

        if id != str(_NOT_FOUND):

            # Domain ID
            domainID = self.menu.addAction(f"{domain_kind} {id}")
            domainID.setDisabled(True)

            # Domain Name (if any)
            if domain[id].name:
                domainName = self.menu.addAction(domain[id].name)
                domainName.setDisabled(True)

            self.menu.addSeparator()
            self.menu.addAction(self.mw.undoAction)
            self.menu.addAction(self.mw.redoAction)
            self.menu.addSeparator()

            colorAction = self.menu.addAction(f'Edit {domain_kind} Color...')
            colorAction.setDisabled(self.model.currentView.highlighting)
            colorAction.setToolTip(f'Edit {domain_kind} color')
            colorAction.setStatusTip(f'Edit {domain_kind} color')
            colorAction.triggered.connect(lambda :
                self.mw.editDomainColor(domain_kind, id))

            maskAction = self.menu.addAction(f'Mask {domain_kind}')
            maskAction.setCheckable(True)
            maskAction.setChecked(domain[id].masked)
            maskAction.setDisabled(not self.model.currentView.masking)
            maskAction.setToolTip(f'Toggle {domain_kind} mask')
            maskAction.setStatusTip(f'Toggle {domain_kind} mask')
            maskAction.triggered[bool].connect(lambda bool=bool:
                self.mw.toggleDomainMask(bool, domain_kind, id))

            highlightAction = self.menu.addAction(f'Highlight {domain_kind}')
            highlightAction.setCheckable(True)
            highlightAction.setChecked(domain[id].highlighted)
            highlightAction.setDisabled(not self.model.currentView.highlighting)
            highlightAction.setToolTip(f'Toggle {domain_kind} highlight')
            highlightAction.setStatusTip(f'Toggle {domain_kind} highlight')
            highlightAction.triggered[bool].connect(lambda bool=bool:
                self.mw.toggleDomainHighlight(bool, domain_kind, id))

        else:
            self.menu.addAction(self.mw.undoAction)
            self.menu.addAction(self.mw.redoAction)
            self.menu.addSeparator()
            bgColorAction = self.menu.addAction('Edit Background Color...')
            bgColorAction.setToolTip('Edit background color')
            bgColorAction.setStatusTip('Edit plot background color')
            bgColorAction.triggered.connect(lambda :
                self.mw.editBackgroundColor(apply=True))

        self.menu.addSeparator()
        self.menu.addAction(self.mw.saveImageAction)
        self.menu.addAction(self.mw.saveViewAction)
        self.menu.addAction(self.mw.openAction)
        self.menu.addSeparator()
        self.menu.addMenu(self.mw.basisMenu)
        self.menu.addMenu(self.mw.colorbyMenu)
        self.menu.addSeparator()
        self.menu.addAction(self.mw.maskingAction)
        self.menu.addAction(self.mw.highlightingAct)
        self.menu.addSeparator()
        self.menu.addAction(self.mw.dockAction)

        self.mw.maskingAction.setChecked(self.model.currentView.masking)
        self.mw.highlightingAct.setChecked(self.model.currentView.highlighting)

        if self.mw.dock.isVisible():
            self.mw.dockAction.setText('Hide &Dock')
        else:
            self.mw.dockAction.setText('Show &Dock')

        self.menu.exec_(event.globalPos())

    def setPixmap(self, w, h):

        # clear out figure
        self.figure.clear()

        cv = self.model.currentView
        # set figure bg color to match window
        window_background = self.parent.palette().color(QtGui.QPalette.Background)
        self.figure.patch.set_facecolor(rgb_normalize(window_background.getRgb()))
        # set figure width
        self.figure.set_figwidth(0.99 * w / self.figure.get_dpi())
        self.figure.set_figheight(0.99 * h / self.figure.get_dpi())
        # set data extents for automatic reporting of pointer location
        data_bounds = [cv.origin[self.mw.xBasis] - cv.width/2.,
                       cv.origin[self.mw.xBasis] + cv.width/2.,
                       cv.origin[self.mw.yBasis] - cv.height/2.,
                       cv.origin[self.mw.yBasis] + cv.height/2.]

        # make sure we have an image to load
        if not hasattr(self.model,'image'):
            self.model.generatePlot()

        if cv.colorby in ('material', 'cell'):
            c = self.figure.subplots().imshow(self.model.image,
                                              extent=data_bounds,
                                              alpha=cv.plotAlpha)
        else:

            idx = 0 if cv.colorby == 'temperature' else 1
            cmap = 'Oranges' if cv.colorby == 'temperature' else 'Greys'
            cmap_label = "Temperature (K)" if cv.colorby == 'temperature' else "Density (g/ccm)"
            c = self.figure.subplots().imshow(self.model.properties[:,:,idx],
                                              cmap=cmap,
                                              extent=data_bounds,
                                              alpha=cv.plotAlpha)
            cmap_ax = self.figure.add_axes([0.95, 0.1, 0.03, 0.8])
            cb = self.figure.colorbar(c, cax=cmap_ax, anchor=(1.0,0.0))
            cb.ax.set_ylabel(cmap_label, rotation=-90, va='bottom', ha='right')


        self.ax = self.figure.axes[0]


        self.ax.margins(0.0, 0.0)

        # set axis labels
        axis_label_str = "{} (cm)"
        self.ax.set_xlabel(axis_label_str.format(cv.basis[0]))
        self.ax.set_ylabel(axis_label_str.format(cv.basis[1]))

        self.draw()



class OptionsDock(QDockWidget):
    def __init__(self, model, FM, parent=None):
        super(OptionsDock, self).__init__(parent)

        self.model = model
        self.FM = FM
        self.mw = parent

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding) # Doesn't work?
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea |
                             QtCore.Qt.RightDockWidgetArea)

        # Create Controls
        self.createOriginBox()
        self.createOptionsBox()
        self.createResolutionBox()

        # Create submit button
        self.applyButton = QPushButton("Apply Changes")
        self.applyButton.setMinimumHeight(self.FM.height() * 1.6) # Mac bug fix
        self.applyButton.clicked.connect(self.mw.applyChanges)

        # Create Zoom box
        self.zoomBox = QSpinBox()
        self.zoomBox.setSuffix(' %')
        self.zoomBox.setRange(25, 2000)
        self.zoomBox.setValue(100)
        self.zoomBox.setSingleStep(25)
        self.zoomBox.valueChanged.connect(self.mw.editZoom)
        self.zoomLayout = QHBoxLayout()
        self.zoomLayout.addWidget(QLabel('Zoom:'))
        self.zoomLayout.addWidget(self.zoomBox)
        self.zoomLayout.setContentsMargins(0,0,0,0)
        self.zoomWidget = QWidget()
        self.zoomWidget.setLayout(self.zoomLayout)

        # Create Layout
        self.dockLayout = QVBoxLayout()
        self.dockLayout.addWidget(self.originGroupBox)
        self.dockLayout.addWidget(self.optionsGroupBox)
        self.dockLayout.addWidget(self.resGroupBox)
        self.dockLayout.addWidget(self.applyButton)
        self.dockLayout.addStretch()
        self.dockLayout.addWidget(HorizontalLine())
        self.dockLayout.addWidget(self.zoomWidget)

        self.optionsWidget = QWidget()
        self.optionsWidget.setLayout(self.dockLayout)
        self.setWidget(self.optionsWidget)

    def createOriginBox(self):

        # X Origin
        self.xOrBox = QDoubleSpinBox()
        self.xOrBox.setDecimals(9)
        self.xOrBox.setRange(-99999, 99999)
        self.xOrBox.valueChanged.connect(lambda value:
            self.mw.editSingleOrigin(value, 0))

        # Y Origin
        self.yOrBox = QDoubleSpinBox()
        self.yOrBox.setDecimals(9)
        self.yOrBox.setRange(-99999, 99999)
        self.yOrBox.valueChanged.connect(lambda value:
            self.mw.editSingleOrigin(value, 1))

        # Z Origin
        self.zOrBox = QDoubleSpinBox()
        self.zOrBox.setDecimals(9)
        self.zOrBox.setRange(-99999, 99999)
        self.zOrBox.valueChanged.connect(lambda value:
            self.mw.editSingleOrigin(value, 2))

        # Origin Form Layout
        self.orLayout = QFormLayout()
        self.orLayout.addRow('X:', self.xOrBox)
        self.orLayout.addRow('Y:', self.yOrBox)
        self.orLayout.addRow('Z:', self.zOrBox)
        #self.orLayout.setVerticalSpacing(4)
        self.orLayout.setLabelAlignment(QtCore.Qt.AlignLeft)
        self.orLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Origin Group Box
        self.originGroupBox = QGroupBox('Origin')
        self.originGroupBox.setLayout(self.orLayout)

    def createOptionsBox(self):

        # Width
        self.widthBox = QDoubleSpinBox(self)
        self.widthBox.setRange(.1, 99999)
        self.widthBox.valueChanged.connect(self.mw.editWidth)

        # Height
        self.heightBox = QDoubleSpinBox(self)
        self.heightBox.setRange(.1, 99999)
        self.heightBox.valueChanged.connect(self.mw.editHeight)

        # ColorBy
        self.colorbyBox = QComboBox(self)
        self.colorbyBox.addItem("material")
        self.colorbyBox.addItem("cell")
        self.colorbyBox.addItem("temperature")
        self.colorbyBox.addItem("density")
        self.colorbyBox.currentTextChanged[str].connect(self.mw.editColorBy)

        # Alpha
        self.plotAlphaBox = QDoubleSpinBox(self)
        self.plotAlphaBox.setValue(self.model.activeView.plotAlpha)
        self.plotAlphaBox.setSingleStep(0.05)
        self.plotAlphaBox.setDecimals(2)
        self.plotAlphaBox.setRange(0.0, 1.0)
        self.plotAlphaBox.valueChanged.connect(self.mw.editPlotAlpha)

        # Basis
        self.basisBox = QComboBox(self)
        self.basisBox.addItem("xy")
        self.basisBox.addItem("xz")
        self.basisBox.addItem("yz")
        self.basisBox.currentTextChanged.connect(self.mw.editBasis)

        # Advanced Color Options
        self.colorOptionsButton = QPushButton('Color Options...')
        self.colorOptionsButton.setMinimumHeight(self.FM.height() * 1.6)
        self.colorOptionsButton.clicked.connect(self.mw.showColorDialog)

        # Options Form Layout
        self.opLayout = QFormLayout()
        self.opLayout.addRow('Width:', self.widthBox)
        self.opLayout.addRow('Height:', self.heightBox)
        self.opLayout.addRow('Basis:', self.basisBox)
        self.opLayout.addRow('Color By:', self.colorbyBox)
        self.opLayout.addRow('Plot alpha:', self.plotAlphaBox)
        self.opLayout.addRow(self.colorOptionsButton)
        self.opLayout.setLabelAlignment(QtCore.Qt.AlignLeft)
        self.opLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Options Group Box
        self.optionsGroupBox = QGroupBox('Options')
        self.optionsGroupBox.setLayout(self.opLayout)

    def createResolutionBox(self):

        # Horizontal Resolution
        self.hResBox = QSpinBox(self)
        self.hResBox.setRange(1, 99999)
        self.hResBox.setSingleStep(25)
        self.hResBox.setSuffix(' px')
        self.hResBox.valueChanged.connect(self.mw.editHRes)

        # Vertical Resolution
        self.vResLabel = QLabel('Pixel Height:')
        self.vResBox = QSpinBox(self)
        self.vResBox.setRange(1, 99999)
        self.vResBox.setSingleStep(25)
        self.vResBox.setSuffix(' px')
        self.vResBox.valueChanged.connect(self.mw.editVRes)

        # Ratio checkbox
        self.ratioCheck = QCheckBox("Fixed Aspect Ratio", self)
        self.ratioCheck.stateChanged.connect(self.mw.toggleAspectLock)

        # Resolution Form Layout
        self.resLayout = QFormLayout()
        self.resLayout.addRow(self.ratioCheck)
        self.resLayout.addRow('Pixel Width:', self.hResBox)
        self.resLayout.addRow(self.vResLabel, self.vResBox)
        self.resLayout.setLabelAlignment(QtCore.Qt.AlignLeft)
        self.resLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Resolution Group Box
        self.resGroupBox = QGroupBox("Resolution")
        self.resGroupBox.setLayout(self.resLayout)

    def updateDock(self):
        self.updateOrigin()
        self.updateWidth()
        self.updateHeight()
        self.updateColorBy()
        self.updatePlotAlpha()
        self.updateBasis()
        self.updateAspectLock()
        self.updateHRes()
        self.updateVRes()

    def updateOrigin(self):
        self.xOrBox.setValue(self.model.activeView.origin[0])
        self.yOrBox.setValue(self.model.activeView.origin[1])
        self.zOrBox.setValue(self.model.activeView.origin[2])

    def updateWidth(self):
        self.widthBox.setValue(self.model.activeView.width)

    def updateHeight(self):
        self.heightBox.setValue(self.model.activeView.height)

    def updateColorBy(self):
        self.colorbyBox.setCurrentText(self.model.activeView.colorby)

    def updatePlotAlpha(self):
        self.plotAlphaBox.setValue(self.model.activeView.plotAlpha)

    def updateBasis(self):
        self.basisBox.setCurrentText(self.model.activeView.basis)

    def updateAspectLock(self):
        if self.model.activeView.aspectLock:
            self.ratioCheck.setChecked(True)
            self.vResBox.setDisabled(True)
            self.vResLabel.setDisabled(True)
        else:
            self.ratioCheck.setChecked(False)
            self.vResBox.setDisabled(False)
            self.vResLabel.setDisabled(False)

    def updateHRes(self):
        self.hResBox.setValue(self.model.activeView.h_res)

    def updateVRes(self):
        self.vResBox.setValue(self.model.activeView.v_res)

    def revertToCurrent(self):
        cv = self.model.currentView

        self.xOrBox.setValue(cv.origin[0])
        self.yOrBox.setValue(cv.origin[1])
        self.zOrBox.setValue(cv.origin[2])

        self.widthBox.setValue(cv.width)
        self.heightBox.setValue(cv.height)

    def resizeEvent(self, event):
        self.mw.resizeEvent(event)

    def hideEvent(self, event):
        self.mw.resizeEvent(event)

    def showEvent(self, event):
        self.mw.resizeEvent(event)

    def moveEvent(self, event):
        self.mw.resizeEvent(event)

class ColorDialog(QDialog):
    def __init__(self, model, FM, parent=None):
        super(ColorDialog, self).__init__(parent)

        self.setWindowTitle('Color Options')

        self.model = model
        self.FM = FM
        self.mw = parent

        self.createDialogLayout()

    def createDialogLayout(self):

        self.createGeneralTab()

        self.cellTable = self.createDomainTable(self.mw.cellsModel)
        self.matTable = self.createDomainTable(self.mw.materialsModel)
        self.cellTab = self.createDomainTab(self.cellTable)
        self.matTab = self.createDomainTab(self.matTable)

        self.tabs = QTabWidget()
        self.tabs.setMaximumHeight(800)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tabs.addTab(self.generalTab, 'General')
        self.tabs.addTab(self.cellTab, 'Cells')
        self.tabs.addTab(self.matTab, 'Materials')

        self.createButtonBox()

        self.colorDialogLayout = QVBoxLayout()
        #self.colorDialogLayout.setContentsMargins(0, 0, 0, 0)
        self.colorDialogLayout.addWidget(self.tabs)
        self.colorDialogLayout.addWidget(self.buttonBox)
        self.setLayout(self.colorDialogLayout)

    def createGeneralTab(self):

        # Masking options
        self.maskingCheck = QCheckBox('')
        self.maskingCheck.stateChanged.connect(self.mw.toggleMasking)

        self.maskColorButton = QPushButton()
        self.maskColorButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.maskColorButton.setFixedWidth(self.FM.width("XXXXXXXXXX"))
        self.maskColorButton.setFixedHeight(self.FM.height() * 1.5)
        self.maskColorButton.clicked.connect(self.mw.editMaskingColor)

        # Highlighting options
        self.hlCheck = QCheckBox('')
        self.hlCheck.stateChanged.connect(self.mw.toggleHighlighting)

        self.hlColorButton = QPushButton()
        self.hlColorButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.hlColorButton.setFixedWidth(self.FM.width("XXXXXXXXXX"))
        self.hlColorButton.setFixedHeight(self.FM.height() * 1.5)
        self.hlColorButton.clicked.connect(self.mw.editHighlightColor)

        self.alphaBox = QDoubleSpinBox()
        self.alphaBox.setRange(0, 1)
        self.alphaBox.setSingleStep(.05)
        self.alphaBox.valueChanged.connect(self.mw.editAlpha)

        self.seedBox = QSpinBox()
        self.seedBox.setRange(1, 999)
        self.seedBox.valueChanged.connect(self.mw.editSeed)

        # General options
        self.bgButton = QPushButton()
        self.bgButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.bgButton.setFixedWidth(self.FM.width("XXXXXXXXXX"))
        self.bgButton.setFixedHeight(self.FM.height() * 1.5)
        self.bgButton.clicked.connect(self.mw.editBackgroundColor)

        self.colorbyBox = QComboBox(self)
        self.colorbyBox.addItem("material")
        self.colorbyBox.addItem("cell")
        self.colorbyBox.addItem("temperature")
        self.colorbyBox.addItem("density")

        self.colorbyBox.currentTextChanged[str].connect(self.mw.editColorBy)

        formLayout = QFormLayout()
        formLayout.setAlignment(QtCore.Qt.AlignHCenter)
        formLayout.setFormAlignment(QtCore.Qt.AlignHCenter)
        formLayout.setLabelAlignment(QtCore.Qt.AlignLeft)
        #formLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        formLayout.addRow('Masking:', self.maskingCheck)
        formLayout.addRow('Mask Color:', self.maskColorButton)
        formLayout.addRow(HorizontalLine())
        formLayout.addRow('Highlighting:', self.hlCheck)
        formLayout.addRow('Highlight Color:', self.hlColorButton)
        formLayout.addRow('Highlight Alpha:', self.alphaBox)
        formLayout.addRow('Highlight Seed:', self.seedBox)
        formLayout.addRow(HorizontalLine())
        formLayout.addRow('Background Color:          ', self.bgButton)
        formLayout.addRow('Color Plot By:', self.colorbyBox)

        generalLayout = QHBoxLayout()
        innerWidget = QWidget()
        generalLayout.setAlignment(QtCore.Qt.AlignVCenter)
        innerWidget.setLayout(formLayout)
        generalLayout.addStretch(1)
        generalLayout.addWidget(innerWidget)
        generalLayout.addStretch(1)

        self.generalTab = QWidget()
        self.generalTab.setLayout(generalLayout)

    def createDomainTable(self, domainmodel):

        domainTable = QTableView()
        domainTable.setModel(domainmodel)
        domainTable.setItemDelegate(DomainDelegate(domainTable))
        domainTable.verticalHeader().setVisible(False)
        domainTable.resizeColumnsToContents()
        domainTable.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        domainTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        return domainTable

    def createDomainTab(self, domaintable):

        domainTab = QWidget()
        domainTab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        domainLayout = QVBoxLayout()
        domainLayout.addWidget(domaintable)
        domainTab.setLayout(domainLayout)

        return domainTab

    def createButtonBox(self):

        applyButton = QPushButton("Apply Changes")
        applyButton.clicked.connect(self.mw.applyChanges)
        closeButton = QPushButton("Close")
        closeButton.clicked.connect(self.hide)

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(applyButton)
        buttonLayout.addWidget(closeButton)

        self.buttonBox = QWidget()
        self.buttonBox.setLayout(buttonLayout)

    def updateDialogValues(self):

        self.updateMasking()
        self.updateMaskingColor()
        self.updateHighlighting()
        self.updateHighlightColor()
        self.updateAlpha()
        self.updateSeed()
        self.updateBackgroundColor()
        self.updateColorBy()

        self.updateDomainTabs()

    def updateMasking(self):
        masking = self.model.activeView.masking

        self.maskingCheck.setChecked(masking)
        self.maskColorButton.setDisabled(not masking)

        if masking:
            self.cellTable.showColumn(4)
            self.matTable.showColumn(4)
        else:
            self.cellTable.hideColumn(4)
            self.matTable.hideColumn(4)

    def updateMaskingColor(self):
        color = self.model.activeView.maskBackground
        self.maskColorButton.setStyleSheet("border-radius: 8px;"
                                    "background-color: rgb%s" % (str(color)))

    def updateHighlighting(self):
        highlighting = self.model.activeView.highlighting

        self.hlCheck.setChecked(highlighting)
        self.hlColorButton.setDisabled(not highlighting)
        self.alphaBox.setDisabled(not highlighting)
        self.seedBox.setDisabled(not highlighting)

        if highlighting:
            self.cellTable.showColumn(5)
            self.cellTable.hideColumn(2)
            self.cellTable.hideColumn(3)
            self.matTable.showColumn(5)
            self.matTable.hideColumn(2)
            self.matTable.hideColumn(3)
        else:
            self.cellTable.hideColumn(5)
            self.cellTable.showColumn(2)
            self.cellTable.showColumn(3)
            self.matTable.hideColumn(5)
            self.matTable.showColumn(2)
            self.matTable.showColumn(3)

    def updateHighlightColor(self):
        color = self.model.activeView.highlightBackground
        self.hlColorButton.setStyleSheet("border-radius: 8px;"
                                    "background-color: rgb%s" % (str(color)))

    def updateAlpha(self):
        self.alphaBox.setValue(self.model.activeView.highlightAlpha)

    def updateSeed(self):
        self.seedBox.setValue(self.model.activeView.highlightSeed)

    def updateBackgroundColor(self):
        color = self.model.activeView.plotBackground
        self.bgButton.setStyleSheet("border-radius: 8px;"
                                    "background-color: rgb%s" % (str(color)))

    def updateColorBy(self):
        self.colorbyBox.setCurrentText(self.model.activeView.colorby)

    def updateDomainTabs(self):
        self.cellTable.setModel(self.mw.cellsModel)
        self.matTable.setModel(self.mw.materialsModel)


class HorizontalLine(QFrame):
    def __init__(self):
        super(HorizontalLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
