#!/usr/bin/python3
# -*- coding: utf-8 -*-

import time
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QApplication, QGroupBox, QFormLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QSizePolicy, QSpacerItem, QMainWindow,
    QCheckBox, QScrollArea, QLayout, QRubberBand, QMenu, QAction, QMenuBar,
    QFileDialog, QDialog, QTabWidget, QGridLayout, QToolButton, QColorDialog,
    QDialogButtonBox, QFrame, QActionGroup, QDockWidget, QTableView,
    QItemDelegate, QHeaderView)
from plotmodel import DomainTableModel, DomainDelegate

class PlotImage(QLabel):
    def __init__(self, model, controller, FM):
        super(PlotImage, self).__init__()

        self.FM = FM

        self.model = model
        self.cont = controller

        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMouseTracking(True)

        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        self.bandOrigin = QtCore.QPoint()
        self.xPlotOrigin = None
        self.yPlotOrigin = None

        self.menu = QMenu(self)

    def enterEvent(self, event):
        self.setCursor(QtCore.Qt.CrossCursor)
        self.cont.coordLabel.show()

    def leaveEvent(self, event):
        self.cont.showStatusPlot()
        self.cont.coordLabel.hide()

    def mousePressEvent(self, event):

        # Set rubber band absolute and relative position
        self.bandOrigin = event.pos()
        self.xPlotOrigin, self.yPlotOrigin = self.getPlotCoords(event.pos())

        # Create rubber band
        self.rubberBand.setGeometry(QtCore.QRect(self.bandOrigin, QtCore.QSize()))

        QLabel.mousePressEvent(self, event)

    def mouseDoubleClickEvent(self, event):

        xCenter, yCenter = self.getPlotCoords(event.pos())
        self.cont.editPlotOrigin(xCenter, yCenter, apply=True)

        QLabel.mouseDoubleClickEvent(self, event)

    def mouseMoveEvent(self, event):

        # Show Cursor position relative to plot in status bar
        xPlotPos, yPlotPos = self.getPlotCoords(event.pos())
        self.cont.showCoords(xPlotPos, yPlotPos)

        # Show Cell/Material ID, Name in status bar
        id, domain, domain_kind = self.getIDinfo(event)
        if id != '-1' and domain[id].name:
            domainInfo = f"{domain_kind} {id}: {domain[id].name}"
        elif id != '-1':
            domainInfo = f"{domain_kind} {id}"
        else:
            domainInfo = ""
        self.cont.statusBar().showMessage(f" {domainInfo}")

        # Update rubber band and values if mouse button held down
        if event.buttons() == QtCore.Qt.LeftButton:
            self.rubberBand.setGeometry(
                QtCore.QRect(self.bandOrigin, event.pos()).normalized())

            # Show rubber band if both dimensions > 10 pixels
            if self.rubberBand.width() > 10 and self.rubberBand.height() > 10:
                self.rubberBand.show()
            else:
                self.rubberBand.hide()

            # Update plot X Origin
            xCenter = (self.xPlotOrigin + xPlotPos) / 2
            yCenter = (self.yPlotOrigin + yPlotPos) / 2
            self.cont.editPlotOrigin(xCenter, yCenter)

            modifiers = QApplication.keyboardModifiers()

            # Zoom out if Shift held
            if modifiers == QtCore.Qt.ShiftModifier:
                cv = self.model.currentView
                bandwidth = abs(self.bandOrigin.x() - event.pos().x())
                width = cv.width * (cv.hRes / max(bandwidth, .001))
                bandheight = abs(self.bandOrigin.y() - event.pos().y())
                height = cv.height * (cv.vRes / max(bandheight, .001))
            else: # Zoom in
                width = max(abs(self.xPlotOrigin - xPlotPos), 1)
                height = max(abs(self.yPlotOrigin - yPlotPos), 1)

            self.cont.editWidth(width)
            self.cont.editHeight(height)

    def mouseReleaseEvent(self, event):

        if self.rubberBand.isVisible():
            self.rubberBand.hide()
            self.cont.applyChanges()
        else:
            self.cont.revertDockControls()

    def contextMenuEvent(self, event):

        self.menu.clear()

        id, domain, domain_kind = self.getIDinfo(event)

        if id != '-1':

            # Domain ID
            domainID = self.menu.addAction(f"{domain_kind} {id}")
            domainID.setDisabled(True)

            # Domain Name (if any)
            if domain[id].name:
                domainName = self.menu.addAction(domain[id].name)
                domainName.setDisabled(True)

            self.menu.addSeparator()
            self.menu.addAction(self.cont.undoAction)
            self.menu.addAction(self.cont.redoAction)
            self.menu.addSeparator()

            colorAction = self.menu.addAction(f'Edit {domain_kind} Color...')
            colorAction.triggered.connect(lambda :
                self.cont.editDomainColor(domain_kind, id))

            maskAction = self.menu.addAction(f'Mask {domain_kind}')
            maskAction.setCheckable(True)
            maskAction.setChecked(domain[id].masked)
            maskAction.setDisabled(not self.model.currentView.masking)
            maskAction.triggered[bool].connect(lambda bool=bool:
                self.cont.toggleDomainMask(bool, domain_kind, id))

            highlightAction = self.menu.addAction(f'Highlight {domain_kind}')
            highlightAction.setCheckable(True)
            highlightAction.setChecked(domain[id].highlighted)
            highlightAction.setDisabled(not self.model.currentView.highlighting)
            highlightAction.triggered[bool].connect(lambda bool=bool:
                self.cont.toggleDomainHighlight(bool, domain_kind, id))

        else:
            self.menu.addAction(self.cont.undoAction)
            self.menu.addAction(self.cont.redoAction)
            self.menu.addSeparator()
            bgColorAction = self.menu.addAction('Edit Background Color...')
            bgColorAction.triggered.connect(lambda :
                self.cont.editBackgroundColor(apply=True))

        self.menu.addSeparator()
        self.menu.addAction(self.cont.saveAction)
        self.menu.addSeparator()
        self.menu.addMenu(self.cont.basisMenu)
        self.menu.addMenu(self.cont.colorbyMenu)
        self.menu.addSeparator()
        self.menu.addAction(self.cont.maskingAction)
        self.menu.addAction(self.cont.highlightingAct)
        self.menu.addSeparator()
        self.menu.addAction(self.cont.dockAction)

        self.cont.maskingAction.setChecked(self.model.currentView.masking)
        self.cont.highlightingAct.setChecked(self.model.currentView.highlighting)

        if self.cont.dock.isVisible():
            self.cont.dockAction.setText('Hide Options &Dock')
        else:
            self.cont.dockAction.setText('Show Options &Dock')

        self.menu.exec_(event.globalPos())

    def getPlotCoords(self, pos):

        cv = self.model.currentView

        # Cursor position in pixels relative to center of plot image
        xPos = pos.x() - (cv.hRes / 2)
        yPos = -pos.y() + (cv.vRes / 2)

        # Curson position in plot coordinates
        xPlotCoord = (xPos / self.cont.scale[0]) + cv.origin[self.cont.xBasis]
        yPlotCoord = (yPos / self.cont.scale[1]) + cv.origin[self.cont.yBasis]

        return (xPlotCoord, yPlotCoord)

    def getIDinfo(self, event):

        if event.pos().y() < self.model.currentView.vRes \
            and event.pos().x() < self.model.currentView.hRes:
            id = f"{self.model.ids[event.pos().y()][event.pos().x()]}"
        else:
            id = '-1'

        if self.model.currentView.colorby == 'cell':
            domain = self.model.activeView.cells
            domain_kind = 'Cell'
        else:
            domain = self.model.activeView.materials
            domain_kind = 'Material'

        return id, domain, domain_kind


class OptionsDock(QDockWidget):
    def __init__(self, model, controller, FM):
        super(OptionsDock, self).__init__()

        self.model = model
        self.cont = controller
        self.FM = FM

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea |
                             QtCore.Qt.RightDockWidgetArea)

        # Create Controls
        self.createOriginBox()
        self.createOptionsBox()
        self.createResolutionBox()

        # Create submit button
        self.submitButton = QPushButton("Apply Changes", self)
        self.submitButton.setMinimumHeight(self.FM.height() * 2)
        self.submitButton.clicked.connect(self.cont.applyChanges)

        # Create Layout
        self.controlLayout = QVBoxLayout()
        self.controlLayout.addWidget(self.originGroupBox)
        self.controlLayout.addWidget(self.optionsGroupBox)
        self.controlLayout.addWidget(self.resGroupBox)
        self.controlLayout.addWidget(self.submitButton)
        self.controlLayout.addStretch()

        self.optionsWidget = QWidget()
        self.optionsWidget.setLayout(self.controlLayout)

        self.setWidget(self.optionsWidget)

    ''' Create GUI Elements '''

    def createOriginBox(self):

        cv = self.model.currentView

        # X Origin
        self.xOrBox = QDoubleSpinBox()
        self.xOrBox.setDecimals(9)
        self.xOrBox.setRange(-99999, 99999)
        self.xOrBox.valueChanged.connect(lambda value:
            self.cont.editSingleOrigin(value, 0))

        # Y Origin
        self.yOrBox = QDoubleSpinBox()
        self.yOrBox.setDecimals(9)
        self.yOrBox.setRange(-99999, 99999)
        self.yOrBox.valueChanged.connect(lambda value:
            self.cont.editSingleOrigin(value, 1))

        # Z Origin
        self.zOrBox = QDoubleSpinBox()
        self.zOrBox.setDecimals(9)
        self.zOrBox.setRange(-99999, 99999)
        self.zOrBox.valueChanged.connect(lambda value:
            self.cont.editSingleOrigin(value, 2))

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

        cv = self.model.currentView

        # Width
        self.widthBox = QDoubleSpinBox(self)
        self.widthBox.setRange(.1, 99999)
        self.widthBox.valueChanged.connect(self.cont.editWidth)

        # Height
        self.heightBox = QDoubleSpinBox(self)
        self.heightBox.setRange(.1, 99999)
        self.heightBox.valueChanged.connect(self.cont.editHeight)

        # ColorBy
        self.colorbyBox = QComboBox(self)
        self.colorbyBox.addItem("material")
        self.colorbyBox.addItem("cell")
        self.colorbyBox.currentTextChanged[str].connect(self.cont.editColorBy)

        # Basis
        self.basisBox = QComboBox(self)
        self.basisBox.addItem("xy")
        self.basisBox.addItem("xz")
        self.basisBox.addItem("yz")
        self.basisBox.currentTextChanged.connect(self.cont.editBasis)

        # Advanced Color Options
        self.colorOptionsButton = QPushButton('Color Options...')
        self.colorOptionsButton.setMinimumHeight(self.FM.height() * 2)
        self.colorOptionsButton.clicked.connect(self.cont.showColorDialog)

        # Options Form Layout
        self.opLayout = QFormLayout()
        self.opLayout.addRow('Width:', self.widthBox)
        self.opLayout.addRow('Height:', self.heightBox)
        self.opLayout.addRow('Basis:', self.basisBox)
        self.opLayout.addRow('Color By:', self.colorbyBox)
        self.opLayout.addRow(self.colorOptionsButton)
        #self.opLayout.setVerticalSpacing(4)
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
        self.hResBox.valueChanged.connect(self.cont.editHRes)

        # Vertical Resolution
        self.vResLabel = QLabel('Pixel Height:')
        self.vResBox = QSpinBox(self)
        self.vResBox.setRange(1, 99999)
        self.vResBox.setSingleStep(25)
        self.vResBox.valueChanged.connect(self.cont.editVRes)

        # Ratio checkbox
        self.ratioCheck = QCheckBox("Fixed Aspect Ratio", self)
        self.ratioCheck.stateChanged.connect(self.cont.toggleAspectLock)

        # Resolution Form Layout
        self.resLayout = QFormLayout()
        self.resLayout.addRow(self.ratioCheck)
        self.resLayout.addRow('Pixel Width:', self.hResBox)
        self.resLayout.addRow(self.vResLabel, self.vResBox)
        #self.resLayout.setVerticalSpacing(4)
        self.resLayout.setLabelAlignment(QtCore.Qt.AlignLeft)
        self.resLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Resolution Group Box
        self.resGroupBox = QGroupBox("Resolution")
        self.resGroupBox.setLayout(self.resLayout)

    ''' Update GUI '''

    def updateDock(self):
        self.updateOrigin()
        self.updateWidth()
        self.updateHeight()
        self.updateColorBy()
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
        self.hResBox.setValue(self.model.activeView.hRes)

    def updateVRes(self):
        self.vResBox.setValue(self.model.activeView.vRes)

    def revertToCurrent(self):
        cv = self.model.currentView

        self.xOrBox.setValue(cv.origin[0])
        self.yOrBox.setValue(cv.origin[1])
        self.zOrBox.setValue(cv.origin[2])

        self.widthBox.setValue(cv.width)
        self.heightBox.setValue(cv.height)


class ColorDialog(QDialog):
    def __init__(self, model, controller, FM, parent=None):
        super(ColorDialog, self).__init__(parent)

        start = time.time()
        self.setWindowTitle('Advanced Color Options')
        #self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.FM = FM

        self.model = model
        self.cont = controller

        self.matColorButtons = {}
        self.matColorLabels = {}
        self.matMaskedChecks = {}
        self.matHighlightChecks = {}

        self.cellColorButtons = {}
        self.cellColorLabels = {}
        self.cellMaskedChecks = {}
        self.cellHighlightChecks = {}

        self.colorHeaders = []
        self.maskHeaders = []
        self.highlightHeaders = []

        self.createDialogLayout()

        print (f"Dialog created in: {round(time.time() - start, 5)} seconds")

    ''' Create GUI Elements'''

    def createDialogLayout(self):

        self.colorDialogLayout = QVBoxLayout()

        # Tabs
        self.createGeneralTab()
        self.createDomainTabs()

        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(500)
        self.tabs.setMaximumHeight(600)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tabs.addTab(self.generalTab, 'General')
        self.tabs.addTab(self.cellTab, 'Cells')
        self.tabs.addTab(self.matTab, 'Materials')

        self.createButtonBox()

        self.colorDialogLayout.addWidget(self.tabs)
        #self.colorDialogLayout.addStretch(1)
        self.colorDialogLayout.addWidget(self.buttonBox)
        self.setLayout(self.colorDialogLayout)

    def createGeneralTab(self):

        # Masking options
        self.maskingCheck = QCheckBox('')
        self.maskingCheck.stateChanged.connect(self.cont.toggleMasking)

        self.maskColorButton = QPushButton()
        self.maskColorButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.maskColorButton.setFixedWidth(self.FM.width("XXXXXXXXXX"))
        self.maskColorButton.setFixedHeight(self.FM.height() * 1.5)
        self.maskColorButton.clicked.connect(self.cont.editMaskingColor)

        # Highlighting options
        self.hlCheck = QCheckBox('')
        self.hlCheck.stateChanged.connect(self.cont.toggleHighlighting)

        self.hlColorButton = QPushButton()
        self.hlColorButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.hlColorButton.setFixedWidth(self.FM.width("XXXXXXXXXX"))
        self.hlColorButton.setFixedHeight(self.FM.height() * 1.5)
        self.hlColorButton.clicked.connect(self.cont.editHighlightColor)

        self.alphaBox = QDoubleSpinBox()
        self.alphaBox.setRange(0, 1)
        self.alphaBox.setSingleStep(.05)
        self.alphaBox.valueChanged.connect(self.cont.editAlpha)

        self.seedBox = QSpinBox()
        self.seedBox.setRange(1, 999)
        self.seedBox.valueChanged.connect(self.cont.editSeed)

        # General options
        self.bgButton = QPushButton()
        self.bgButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.bgButton.setFixedWidth(self.FM.width("XXXXXXXXXX"))
        self.bgButton.setFixedHeight(self.FM.height() * 1.5)
        self.bgButton.clicked.connect(self.cont.editBackgroundColor)

        self.colorbyBox = QComboBox(self)
        self.colorbyBox.addItem("material")
        self.colorbyBox.addItem("cell")
        self.colorbyBox.currentTextChanged[str].connect(self.cont.editColorBy)

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
        formLayout.addRow('Background Color:', self.bgButton)
        formLayout.addRow('Color Plot By:', self.colorbyBox)
        #formLayout.addStretch(1)

        generalLayout = QHBoxLayout()
        innerWidget = QWidget()
        innerWidget.setLayout(formLayout)
        generalLayout.addStretch(1)
        generalLayout.addWidget(innerWidget)
        generalLayout.addStretch(1)

        self.generalTab = QWidget()
        self.generalTab.setLayout(generalLayout)

    def createDomainTabs(self):
        self.cellTable = QTableView()
        self.cellTable.setModel(self.cont.cellsModel)
        self.cellTable.setItemDelegate(DomainDelegate(self))
        self.cellTable.verticalHeader().setVisible(False)
        self.cellTable.resizeColumnsToContents()
        self.cellTable.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cellTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        self.cellTab = QWidget()
        self.cellTab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cellTab.setMaximumHeight(700)
        self.cellLayout = QVBoxLayout()
        self.cellLayout.addWidget(self.cellTable)
        self.cellTab.setLayout(self.cellLayout)

        self.matTable = QTableView()
        self.matTable.setModel(self.cont.materialsModel)
        self.matTable.setItemDelegate(DomainDelegate(self))
        self.matTable.verticalHeader().setVisible(False)
        self.matTable.resizeColumnsToContents()
        self.matTable.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.matTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        self.matTab = QWidget()
        self.matTab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        #self.matTab.setMinimumWidth(self.matTable.width() + 20)
        self.matTab.setMaximumHeight(700)
        self.matLayout = QVBoxLayout()
        self.matLayout.addWidget(self.matTable)
        self.matTab.setLayout(self.matLayout)

    def createButtonBox(self):

        applyButton = QPushButton("Apply Changes")
        applyButton.clicked.connect(self.cont.applyChanges)
        closeButton = QPushButton("Close")
        closeButton.clicked.connect(self.hide)

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(applyButton)
        buttonLayout.addWidget(closeButton)

        self.buttonBox = QWidget()
        self.buttonBox.setLayout(buttonLayout)

    ''' Update GUI Elements'''

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

    def updateMaskingColor(self):
        color = self.model.activeView.maskBackground
        self.maskColorButton.setStyleSheet("border-radius: 8px;"
                                    "background-color: rgb%s" % (str(color)))

    def updateHighlighting(self):
        highlighting = self.model.activeView.highlighting

        self.hlCheck.setChecked(highlighting)
        self.hlColorButton.setDisabled(not highlighting)

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
        self.cellTable.setModel(self.cont.cellsModel)
        self.matTable.setModel(self.cont.materialsModel)


class HorizontalLine(QFrame):
    def __init__(self):
        super(HorizontalLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
