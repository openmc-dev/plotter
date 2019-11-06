from functools import partial

from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
                               QGroupBox, QFormLayout, QLabel,
                               QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                               QSizePolicy, QSpacerItem, QMainWindow, QCheckBox,
                               QDialog, QTabWidget, QGridLayout,
                               QToolButton, QColorDialog, QDockWidget,
                               QItemDelegate, QHeaderView, QSlider,
                               QTextEdit, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem)
from matplotlib import cm as mcolormaps

from openmc.filter import (UniverseFilter, MaterialFilter, CellFilter,
                           SurfaceFilter, MeshFilter, MeshSurfaceFilter)

from common_widgets import HorizontalLine

_SPATIAL_FILTERS = (UniverseFilter, MaterialFilter, CellFilter,
                    SurfaceFilter, MeshFilter, MeshSurfaceFilter)

class PlotterDock(QDockWidget):

    def __init__(self, model, FM, parent=None):
        super().__init__(parent)

        self.model = model
        self.FM = FM
        self.mw = parent

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea |
                             QtCore.Qt.RightDockWidgetArea)

class OptionsDock(PlotterDock):
    def __init__(self, model, FM, parent=None):
        super().__init__(model, FM, parent)

        self.model = model
        self.FM = FM
        self.mw = parent

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea |
                             QtCore.Qt.RightDockWidgetArea)

        # Create Controls
        self.createOriginBox()
        self.createOptionsBox()
        self.createResolutionBox()

        # Create submit button
        self.applyButton = QPushButton("Apply Changes")
        # Mac bug fix
        self.applyButton.setMinimumHeight(self.FM.height() * 1.6)
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
        self.zoomLayout.setContentsMargins(0, 0, 0, 0)
        self.zoomWidget = QWidget()
        self.zoomWidget.setLayout(self.zoomLayout)

        # Create Layout
        self.dockLayout = QVBoxLayout()
        self.dockLayout.addWidget(self.originGroupBox)
        self.dockLayout.addWidget(self.optionsGroupBox)
        self.dockLayout.addWidget(self.resGroupBox)
        self.dockLayout.addWidget(HorizontalLine())
        self.dockLayout.addWidget(self.zoomWidget)
        self.dockLayout.addWidget(HorizontalLine())
        self.dockLayout.addStretch()
        self.dockLayout.addWidget(self.applyButton)
        self.dockLayout.addWidget(HorizontalLine())

        self.optionsWidget = QWidget()
        self.optionsWidget.setLayout(self.dockLayout)
        self.setWidget(self.optionsWidget)

    def createOriginBox(self):

        # X Origin
        self.xOrBox = QDoubleSpinBox()
        self.xOrBox.setDecimals(9)
        self.xOrBox.setRange(-99999, 99999)
        xbox_connector = partial(self.mw.editSingleOrigin,
                                 dimension=0)
        self.xOrBox.valueChanged.connect(xbox_connector)

        # Y Origin
        self.yOrBox = QDoubleSpinBox()
        self.yOrBox.setDecimals(9)
        self.yOrBox.setRange(-99999, 99999)
        ybox_connector = partial(self.mw.editSingleOrigin,
                                 dimension=1)
        self.yOrBox.valueChanged.connect(ybox_connector)

        # Z Origin
        self.zOrBox = QDoubleSpinBox()
        self.zOrBox.setDecimals(9)
        self.zOrBox.setRange(-99999, 99999)
        zbox_connector = partial(self.mw.editSingleOrigin,
                                 dimension=2)
        self.zOrBox.valueChanged.connect(zbox_connector)

        # Origin Form Layout
        self.orLayout = QFormLayout()
        self.orLayout.addRow('X:', self.xOrBox)
        self.orLayout.addRow('Y:', self.yOrBox)
        self.orLayout.addRow('Z:', self.zOrBox)
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

        # Visibility
        self.visibilityBox = QCheckBox(self)
        self.visibilityBox.stateChanged.connect(self.mw.editPlotVisibility)

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
        self.opLayout.addRow('Visible:', self.visibilityBox)
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
        self.updatePlotVisibility()
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

    def updatePlotVisibility(self):
        self.visibilityBox.setChecked(self.model.activeView.plotVisibility)

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


class TallyDock(PlotterDock):

    def __init__(self, model, FM, parent=None):
        super().__init__(model, FM, parent)

        self.tally_map = {}
        self.filter_map = {}
        self.score_map = {}
        self.nuclide_map = {}

        self.createTallySelectionLayout()

        self.dockLayout = QVBoxLayout()

        self.widget = QWidget()
        self.widget.setLayout(self.dockLayout)
        self.setWidget(self.widget)

        # Create submit button
        self.applyButton = QPushButton("ApplyChanges")
        self.applyButton.setMinimumHeight(self.FM.height() * 1.6)
        self.applyButton.clicked.connect(self.mw.applyChanges)

        self.dockLayout.addWidget(self.tallyGroupBox)
        self.dockLayout.addStretch()

        self.tallyColorForm = ColorForm(self.model, self.mw, 'tally')

        self.scoresListWidget = QListWidget()
        self.nuclideListWidget = QListWidget()

        self.dockLayout.addWidget(HorizontalLine())
        self.dockLayout.addWidget(self.tallyColorForm)
        self.dockLayout.addWidget(HorizontalLine())
        self.dockLayout.addWidget(self.applyButton)
        self.update()

    def createTallySelectionLayout(self):

        self.formLayout = QFormLayout()

        # Tally listing
        self.tallySelector = QComboBox(self)
        self.tallySelector.currentTextChanged[str].connect(self.mw.editSelectedTally)

        self.formLayout.addRow(self.tallySelector)
        self.formLayout.setLabelAlignment(QtCore.Qt.AlignLeft)
        self.formLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # tally group box
        self.tallyGroupBox = QGroupBox('Tally')
        self.tallyGroupBox.setLayout(self.formLayout)

    def updateMinMax(self):
        self.tallyColorForm.updateMinMax()

    def create_filter_tree(self, spatial_filters):
        tally = self.model.statepoint.tallies[self.model.selectedTally]
        filters = tally.filters

        # create a tree for the filters
        self.filterTree = QTreeWidget()
        header = QTreeWidgetItem(["Filters"])
        self.filterTree.setHeaderItem(header)
        self.filterTree.setItemHidden(header, True)
        self.filterTree.setColumnCount(1)

        self.filter_map = {}
        self.bin_map = {}

        for filter in filters:
            filter_label = str(type(filter)).split(".")[-1][:-2]
            filter_item = QTreeWidgetItem(self.filterTree, [filter_label,])
            self.filter_map[filter] = filter_item

            if isinstance(filter, MeshFilter):
                continue
            # make checkable
            if not spatial_filters:
                filter_item.setFlags(QtCore.Qt.ItemIsUserCheckable)
            else:
                filter_item.setFlags(filter_item.flags() | QtCore.Qt.ItemIsTristate | QtCore.Qt.ItemIsUserCheckable)
            filter_item.setCheckState(0, QtCore.Qt.Unchecked)

            for bin in filter.bins:
                item = QTreeWidgetItem(filter_item, [str(bin),])
                if not spatial_filters:
                    item.setFlags(QtCore.Qt.ItemIsUserCheckable)
                else:
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Unchecked)
                self.bin_map[(filter, bin)] = item

    def selectTally(self, tally_label=None):
        av = self.model.activeView
        # reset form layout
        for i in reversed(range(self.formLayout.count())):
            self.formLayout.itemAt(i).widget().setParent(None)
        # always re-add the tally selector
        self.formLayout.addRow(self.tallySelector)
        self.formLayout.addRow(HorizontalLine())

        if tally_label is None or tally_label == "None" or tally_label == "":
            self.model.selectedTally = None
            av.tallyValue = None
        else:
            tally_id = int(tally_label.split()[1])
            tally = self.model.statepoint.tallies[tally_id]
            self.model.selectedTally = tally_id

            filter_types = set()
            for filter in tally.filters:
                filter_types.add(type(filter))
            spatial_filters = bool(len(filter_types.intersection(_SPATIAL_FILTERS)))

            self.formLayout.addRow(QLabel("Filters:"))

            if not spatial_filters:
                self.filter_description = QLabel("(No Spatial Filters)")
                self.formLayout.addRow(self.filter_description)

            self.create_filter_tree(spatial_filters)

            self.formLayout.addRow(self.filterTree)


            self.formLayout.addRow(HorizontalLine())

            # value selection
            self.formLayout.addRow(QLabel("Value:"))
            self.valueBox = QComboBox(self)
            self.values = ('Mean', 'Std. Dev.', 'Sum', 'Sum Sq.')
            for value in self.values:
                self.valueBox.addItem(value)
            self.formLayout.addRow(self.valueBox)
            self.valueBox.currentTextChanged[str].connect(self.mw.editTallyValue)
            # set to mean by default
            if self.model.activeView.tallyValue is None:
                av.tallyValue = self.values[0]

            self.formLayout.addRow(HorizontalLine())

            # list for tally scores
            self.formLayout.addRow(QLabel("Scores:"))
            self.scoresListWidget.setSortingEnabled(True)
            self.scoresListWidget.itemClicked.connect(self.mw.updateScores)
            self.score_map.clear()
            self.scoresListWidget.clear()
            for score in tally.scores:
                ql = QListWidgetItem()
                ql.setText(score.capitalize())
                ql.setCheckState(QtCore.Qt.Unchecked)
                if not spatial_filters:
                    ql.setFlags(QtCore.Qt.ItemIsUserCheckable)
                else:
                    ql.setFlags(ql.flags() | QtCore.Qt.ItemIsUserCheckable)
                    ql.setFlags(ql.flags() & ~QtCore.Qt.ItemIsSelectable)
                self.score_map[score] = ql
                self.scoresListWidget.addItem(ql)
            self.formLayout.addRow(self.scoresListWidget)

            self.formLayout.addRow(HorizontalLine())
            self.formLayout.addRow(QLabel("Nuclides:"))

            # list for nuclides
            self.nuclideListWidget.setSortingEnabled(True)
            self.nuclideListWidget.itemClicked.connect(self.mw.updateNuclides)
            self.nuclide_map.clear()
            self.nuclideListWidget.clear()
            for nuclide in tally.nuclides:
                ql = QListWidgetItem()
                ql.setText(nuclide.capitalize())
                ql.setCheckState(QtCore.Qt.Unchecked)
                if not spatial_filters:
                    ql.setFlags(QtCore.Qt.ItemIsUserCheckable)
                else:
                    ql.setFlags(ql.flags() | QtCore.Qt.ItemIsUserCheckable)
                    ql.setFlags(ql.flags() & ~QtCore.Qt.ItemIsSelectable)
                self.nuclide_map[nuclide] = ql
                self.nuclideListWidget.addItem(ql)
            self.formLayout.addRow(self.nuclideListWidget)

    def updateScores(self):
        applied_scores = []
        for score, score_box in self.score_map.items():
            if score_box.checkState() == QtCore.Qt.CheckState.Checked:
                applied_scores.append(score)
        self.model.appliedScores = tuple(applied_scores)

    def updateNuclides(self):
        applied_nuclides = []
        for nuclide, nuclide_box in self.nuclide_map.items():
            if nuclide_box.checkState() == QtCore.Qt.CheckState.Checked:
                applied_nuclides.append(nuclide)
        self.model.appliedNuclides = tuple(applied_nuclides)

    @staticmethod
    def cellFilterForm(filter):
        l = QCheckBox()
        txt = "{}. Cell Filter (IDs: {})"
        ids = map(str, filter.bins)
        l.setText(txt.format(filter.id, ", ".join(ids)))
        return l

    @staticmethod
    def universeFilterForm(filter):
        l = QCheckBox()
        txt = "{}. Universe Filter (IDs: {})"
        ids = map(str, filter.bins)
        l.setText(txt.format(filter.id, ", ".join(ids)))
        return l

    @staticmethod
    def surfaceFilterForm(filter):
        l = QCheckBox()
        txt = "{}. Universe Filter (IDs: {})"
        ids = map(str, filter.bins)
        l.setText(txt.format(filter.id, ", ".join(cells)))
        return l

    def updateColormap(self):
        cmaps = self.model.activeView.colormaps
        for key, val in cmaps.items():
            idx = self.tabs[key].colormapBox.findText(val,
                                                      QtCore.Qt.MatchFixedString)
            if idx >= 0:
                self.tabs[key].colormapBox.setCurrentIndex(idx)

    def update(self):

        self.tallyColorForm.update()

        if self.model.statepoint:
            tally_w_name = 'Tally {} "{}"'
            tally_no_name = 'Tally {}'
            self.tallySelector.setEnabled(True)
            self.tallySelector.addItem("None")
            for idx, tally in enumerate(self.model.statepoint.tallies.values()):
                if tally.name == "":
                    self.tallySelector.addItem(tally_no_name.format(tally.id))
                else:
                    self.tallySelector.addItem(tally_w_name.format(tally.id, tally.name))
                self.tally_map[idx] = tally
        else:
            self.tallySelector.clear()
            self.tallySelector.setDisabled(True)

class ColorForm(QWidget):
    """
    Class for handling a field with a colormap, alpha, and visibility

    Attributes
    ----------

    model : PlotModel instance
        The model instance used when updating information on the form.
    colormapBox : QComboBox instance
        Holds the string of the matplotlib colorbar being used
    visibilityBox : QCheckBox instance
        Indicator for whether or not the field should be visible
    alphaBox : QDoubleSpinBox instance
        Holds the alpha value for the displayed field data
    """
    def __init__(self, model, mw, field, colormaps=None):
        """
        """
        super().__init__()

        self.model = model
        self.mw = mw
        self.field = field

        self.layout = QFormLayout()

        self.colormapBox = QComboBox()
        # populate with colormaps
        if colormaps is None:
            colormaps = sorted(m for m in mcolormaps.datad if not m.endswith("_r"))
        for colormap in colormaps:
            self.colormapBox.addItem(colormap)

        cmap_connector = partial(self.mw.editTallyDataColormap)
        self.colormapBox.currentTextChanged[str].connect(cmap_connector)

        self.layout.addRow("Colormap: ", self.colormapBox)

        self.visibilityBox = QCheckBox()

        visible_connector = partial(self.mw.toggleTallyVisibility)
        self.visibilityBox.stateChanged.connect(visible_connector)

        self.alphaBox = QDoubleSpinBox()
        self.alphaBox.setDecimals(2)
        alpha_connector = partial(self.mw.editTallyAlpha)
        self.alphaBox.valueChanged.connect(alpha_connector)

        self.userMinMaxBox = QCheckBox()
        minmax_connector = partial(self.mw.toggleTallyDataUserMinMax)
        self.userMinMaxBox.stateChanged.connect(minmax_connector)

        self.minBox = QDoubleSpinBox()
        self.minBox.setMinimum(0.0)
        self.minBox.setMaximum(1.0E9)
        min_connector = partial(self.mw.editTallyDataMin)
        self.minBox.valueChanged.connect(min_connector)

        self.maxBox = QDoubleSpinBox()
        self.maxBox.setMinimum(0.0)
        self.maxBox.setMaximum(1.0E9)
        max_connector = partial(self.mw.editTallyDataMax)
        self.maxBox.valueChanged.connect(max_connector)

        self.scaleBox = QCheckBox()
        scale_connector = partial(self.mw.toggleTallyLogScale)
        self.scaleBox.stateChanged.connect(scale_connector)


        # add widgets to form
        self.layout.addRow("Visible:", self.visibilityBox)
        self.layout.addRow("Alpha: ", self.alphaBox)
        self.layout.addRow("Custom Min/Max: ", self.userMinMaxBox)
        self.layout.addRow("Min: ", self.minBox)
        self.layout.addRow("Max: ", self.maxBox)
        self.layout.addRow("Log Scale: ", self.scaleBox)

        self.setLayout(self.layout)

        self.update()

    def updateMinMax(self):
        cv = self.model.currentView

        if cv.tallyDataUserMinMax:
            self.minBox.setEnabled(True)
            self.maxBox.setEnabled(True)
        else:
            self.minBox.setEnabled(False)
            self.maxBox.setEnabled(False)

    def updateTallyVisibility(self):
        cv = self.model.currentView
        self.visibilityBox.setChecked(cv.tallyDataVisible)

    def updateMinMax(self):
        cv = self.model.currentView
        self.minBox.setValue(cv.tallyDataMin)
        self.maxBox.setValue(cv.tallyDataMax)

    def update(self):
        cv = self.model.currentView

        cmap = cv.tallyDataColormap
        idx = self.colormapBox.findText(cmap, QtCore.Qt.MatchFixedString)
        self.colormapBox.setCurrentIndex(idx)

        self.alphaBox.setValue(cv.tallyDataAlpha)
        self.visibilityBox.setChecked(cv.tallyDataVisible)
        self.userMinMaxBox.setChecked(cv.tallyDataUserMinMax)

        # self.updateMinMax()

        self.scaleBox.setChecked(cv.tallyDataLogScale)

