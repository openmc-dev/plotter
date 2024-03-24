from functools import partial
from collections.abc import Iterable
from collections import defaultdict

from PySide6 import QtCore
from PySide6.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
                               QGroupBox, QFormLayout, QLabel, QLineEdit,
                               QComboBox, QSpinBox, QDoubleSpinBox, QSizePolicy,
                               QCheckBox, QDockWidget, QScrollArea, QListWidget,
                               QListWidgetItem, QTreeWidget, QTreeWidgetItem)
import matplotlib.pyplot as plt
import numpy as np
import openmc

from .custom_widgets import HorizontalLine, Expander
from .scientific_spin_box import ScientificDoubleSpinBox
from .plotmodel import (_SCORE_UNITS, _TALLY_VALUES,
                        _REACTION_UNITS, _SPATIAL_FILTERS)


class PlotterDock(QDockWidget):
    """
    Dock widget with common settings for the plotting application
    """

    def __init__(self, model, font_metric, parent=None):
        super().__init__(parent)

        self.model = model
        self.font_metric = font_metric
        self.main_window = parent

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)


class DomainDock(PlotterDock):
    """
    Domain options dock
    """

    def __init__(self, model, font_metric, parent=None):
        super().__init__(model, font_metric, parent)

        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea)

        # Create Controls
        self._createOriginBox()
        self._createOptionsBox()
        self._createResolutionBox()

        # Create submit button
        self.applyButton = QPushButton("Apply Changes")
        # Mac bug fix
        self.applyButton.setMinimumHeight(self.font_metric.height() * 1.6)
        self.applyButton.clicked.connect(self.main_window.applyChanges)

        # Create Zoom box
        self.zoomBox = QSpinBox()
        self.zoomBox.setSuffix(' %')
        self.zoomBox.setRange(25, 2000)
        self.zoomBox.setValue(100)
        self.zoomBox.setSingleStep(25)
        self.zoomBox.valueChanged.connect(self.main_window.editZoom)
        self.zoomLayout = QHBoxLayout()
        self.zoomLayout.addWidget(QLabel('Zoom:'))
        self.zoomLayout.addWidget(self.zoomBox)
        self.zoomLayout.setContentsMargins(0, 0, 0, 0)
        self.zoomWidget = QWidget()
        self.zoomWidget.setLayout(self.zoomLayout)

        # Create Layout
        self.dockLayout = QVBoxLayout()
        self.dockLayout.addWidget(QLabel("Geometry/Properties"))
        self.dockLayout.addWidget(HorizontalLine())
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

    def _createOriginBox(self):

        # X Origin
        self.xOrBox = QDoubleSpinBox()
        self.xOrBox.setDecimals(9)
        self.xOrBox.setRange(-99999, 99999)
        xbox_connector = partial(self.main_window.editSingleOrigin,
                                 dimension=0)
        self.xOrBox.valueChanged.connect(xbox_connector)

        # Y Origin
        self.yOrBox = QDoubleSpinBox()
        self.yOrBox.setDecimals(9)
        self.yOrBox.setRange(-99999, 99999)
        ybox_connector = partial(self.main_window.editSingleOrigin,
                                 dimension=1)
        self.yOrBox.valueChanged.connect(ybox_connector)

        # Z Origin
        self.zOrBox = QDoubleSpinBox()
        self.zOrBox.setDecimals(9)
        self.zOrBox.setRange(-99999, 99999)
        zbox_connector = partial(self.main_window.editSingleOrigin,
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

    def _createOptionsBox(self):

        # Width
        self.widthBox = QDoubleSpinBox(self)
        self.widthBox.setRange(.1, 99999)
        self.widthBox.setDecimals(9)
        self.widthBox.valueChanged.connect(self.main_window.editWidth)

        # Height
        self.heightBox = QDoubleSpinBox(self)
        self.heightBox.setRange(.1, 99999)
        self.heightBox.setDecimals(9)
        self.heightBox.valueChanged.connect(self.main_window.editHeight)

        # ColorBy
        self.colorbyBox = QComboBox(self)
        self.colorbyBox.addItem("material")
        self.colorbyBox.addItem("cell")
        self.colorbyBox.addItem("temperature")
        self.colorbyBox.addItem("density")
        self.colorbyBox.currentTextChanged[str].connect(
            self.main_window.editColorBy)

        # Universe level (applies to cell coloring only)
        self.universeLevelBox = QComboBox(self)
        self.universeLevelBox.addItem('all')
        for i in range(self.model.max_universe_levels):
            self.universeLevelBox.addItem(str(i))
        self.universeLevelBox.currentTextChanged[str].connect(
            self.main_window.editUniverseLevel)

        # Alpha
        self.domainAlphaBox = QDoubleSpinBox(self)
        self.domainAlphaBox.setValue(self.model.activeView.domainAlpha)
        self.domainAlphaBox.setSingleStep(0.05)
        self.domainAlphaBox.setDecimals(2)
        self.domainAlphaBox.setRange(0.0, 1.0)
        self.domainAlphaBox.valueChanged.connect(
            self.main_window.editPlotAlpha)

        # Visibility
        self.visibilityBox = QCheckBox(self)
        self.visibilityBox.stateChanged.connect(
            self.main_window.editPlotVisibility)

        # Outlines
        self.outlinesBox = QCheckBox(self)
        self.outlinesBox.stateChanged.connect(self.main_window.toggleOutlines)

        # Basis
        self.basisBox = QComboBox(self)
        self.basisBox.addItem("xy")
        self.basisBox.addItem("xz")
        self.basisBox.addItem("yz")
        self.basisBox.currentTextChanged.connect(self.main_window.editBasis)

        # Advanced Color Options
        self.colorOptionsButton = QPushButton('Color Options...')
        self.colorOptionsButton.setMinimumHeight(
            self.font_metric.height() * 1.6)
        self.colorOptionsButton.clicked.connect(
            self.main_window.showColorDialog)

        # Options Form Layout
        self.opLayout = QFormLayout()
        self.opLayout.addRow('Width:', self.widthBox)
        self.opLayout.addRow('Height:', self.heightBox)
        self.opLayout.addRow('Basis:', self.basisBox)
        self.opLayout.addRow('Color By:', self.colorbyBox)
        self.opLayout.addRow('Universe Level:', self.universeLevelBox)
        self.opLayout.addRow('Plot alpha:', self.domainAlphaBox)
        self.opLayout.addRow('Visible:', self.visibilityBox)
        self.opLayout.addRow('Outlines:', self.outlinesBox)
        self.opLayout.addRow(self.colorOptionsButton)
        self.opLayout.setLabelAlignment(QtCore.Qt.AlignLeft)
        self.opLayout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Options Group Box
        self.optionsGroupBox = QGroupBox('Options')
        self.optionsGroupBox.setLayout(self.opLayout)

    def _createResolutionBox(self):

        # Horizontal Resolution
        self.hResBox = QSpinBox(self)
        self.hResBox.setRange(1, 99999)
        self.hResBox.setSingleStep(25)
        self.hResBox.setSuffix(' px')
        self.hResBox.valueChanged.connect(self.main_window.editHRes)

        # Vertical Resolution
        self.vResLabel = QLabel('Pixel Height:')
        self.vResBox = QSpinBox(self)
        self.vResBox.setRange(1, 99999)
        self.vResBox.setSingleStep(25)
        self.vResBox.setSuffix(' px')
        self.vResBox.valueChanged.connect(self.main_window.editVRes)

        # Ratio checkbox
        self.ratioCheck = QCheckBox("Fixed Aspect Ratio", self)
        self.ratioCheck.stateChanged.connect(self.main_window.toggleAspectLock)

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
        self.updateUniverseLevel()
        self.updatePlotAlpha()
        self.updatePlotVisibility()
        self.updateOutlines()
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
        if self.model.activeView.colorby != 'cell':
            self.universeLevelBox.setEnabled(False)
        else:
            self.universeLevelBox.setEnabled(True)

    def updateUniverseLevel(self):
        self.universeLevelBox.setCurrentIndex(self.model.activeView.level + 1)

    def updatePlotAlpha(self):
        self.domainAlphaBox.setValue(self.model.activeView.domainAlpha)

    def updatePlotVisibility(self):
        self.visibilityBox.setChecked(self.model.activeView.domainVisible)

    def updateOutlines(self):
        self.outlinesBox.setChecked(self.model.activeView.outlines)

    def updateBasis(self):
        self.basisBox.setCurrentText(self.model.activeView.basis)

    def updateAspectLock(self):
        aspect_lock = bool(self.model.activeView.aspectLock)
        self.ratioCheck.setChecked(aspect_lock)
        self.vResBox.setDisabled(aspect_lock)
        self.vResLabel.setDisabled(aspect_lock)

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
        self.main_window.resizeEvent(event)

    hideEvent = showEvent = moveEvent = resizeEvent


class TallyDock(PlotterDock):

    def __init__(self, model, font_metric, parent=None):
        super().__init__(model, font_metric, parent)

        self.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)

        # Dock maps for tally information
        self.tally_map = {}
        self.filter_map = {}
        self.score_map = {}
        self.nuclide_map = {}

        # Tally selector
        self.tallySelectorLayout = QFormLayout()
        self.tallySelector = QComboBox(self)
        self.tallySelector.currentTextChanged[str].connect(
            self.main_window.editSelectedTally)
        self.tallySelectorLayout.addRow(self.tallySelector)
        self.tallySelectorLayout.setLabelAlignment(QtCore.Qt.AlignLeft)
        self.tallySelectorLayout.setFieldGrowthPolicy(
            QFormLayout.AllNonFixedFieldsGrow)

        # Add selector to its own box
        self.tallyGroupBox = QGroupBox('Selected Tally')
        self.tallyGroupBox.setLayout(self.tallySelectorLayout)

        # Create submit button
        self.applyButton = QPushButton("Apply Changes")
        self.applyButton.setMinimumHeight(self.font_metric.height() * 1.6)
        self.applyButton.clicked.connect(self.main_window.applyChanges)

        # Color options section
        self.tallyColorForm = ColorForm(self.model, self.main_window, 'tally')
        self.scoresGroupBox = Expander(title="Scores:")
        self.scoresListWidget = QListWidget()
        self.scoresListWidget.itemChanged.connect(self.updateScores)
        self.nuclidesListWidget = QListWidget()

        # Main layout
        self.dockLayout = QVBoxLayout()
        self.dockLayout.addWidget(QLabel("Tallies"))
        self.dockLayout.addWidget(HorizontalLine())
        self.dockLayout.addWidget(self.tallyGroupBox)
        self.dockLayout.addStretch()
        self.dockLayout.addWidget(HorizontalLine())
        self.dockLayout.addWidget(self.tallyColorForm)
        self.dockLayout.addWidget(HorizontalLine())
        self.dockLayout.addWidget(self.applyButton)

        # Create widget for dock and apply main layout
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.widget = QWidget()
        self.widget.setLayout(self.dockLayout)
        self.scroll.setWidget(self.widget)
        self.setWidget(self.scroll)

    def _createFilterTree(self, spatial_filters):
        av = self.model.activeView
        tally = self.model.statepoint.tallies[av.selectedTally]
        filters = tally.filters

        # create a tree for the filters
        self.treeLayout = QVBoxLayout()
        self.filterTree = QTreeWidget()
        self.treeLayout.addWidget(self.filterTree)
        self.treeExpander = Expander("Filters:", layout=self.treeLayout)
        self.treeExpander.expand()  # start with filters expanded

        header = QTreeWidgetItem(["Filters"])
        self.filterTree.setHeaderItem(header)
        header.setHidden(True)
        #self.filterTree.setItemHidden(header, True)
        self.filterTree.setColumnCount(1)

        self.filter_map = {}
        self.bin_map = {}

        for tally_filter in filters:
            filter_label = str(type(tally_filter)).split(".")[-1][:-2]
            filter_item = QTreeWidgetItem(self.filterTree, (filter_label,))
            self.filter_map[tally_filter] = filter_item

            # make checkable
            if not spatial_filters:
                filter_item.setFlags(QtCore.Qt.ItemIsUserCheckable)
                filter_item.setToolTip(
                    0, "Only tallies with spatial filters are viewable.")
            else:
                filter_item.setFlags(
                    filter_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            filter_item.setCheckState(0, QtCore.Qt.Unchecked)

            # all mesh bins are selected by default and not shown in the dock
            if isinstance(tally_filter, openmc.MeshFilter):
                filter_item.setCheckState(0, QtCore.Qt.Checked)
                filter_item.setFlags(QtCore.Qt.ItemIsUserCheckable)
                filter_item.setToolTip(
                    0, "All Mesh bins are selected automatically")
                continue

            def _bin_sort_val(bin):
                if isinstance(bin, Iterable):
                    if all([isinstance(val, float) for val in bin]):
                        return np.sum(bin)
                    else:
                        return tuple(bin)
                else:
                    return bin

            if isinstance(tally_filter, openmc.EnergyFunctionFilter):
                bins = [0]
            else:
                bins = tally_filter.bins

            for bin in sorted(bins, key=_bin_sort_val):
                item = QTreeWidgetItem(filter_item, [str(bin),])
                if not spatial_filters:
                    item.setFlags(QtCore.Qt.ItemIsUserCheckable)
                    item.setToolTip(
                        0, "Only tallies with spatial filters are viewable.")
                else:
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Unchecked)

                bin = bin if not isinstance(bin, Iterable) else tuple(bin)
                self.bin_map[tally_filter, bin] = item

            # start with all filters selected if spatial filters are present
            if spatial_filters:
                filter_item.setCheckState(0, QtCore.Qt.Checked)

    def selectFromModel(self):
        cv = self.model.currentView
        self.selectedTally(cv.selectedTally)

    def selectTally(self, tally_label=None):
        # using active view to populate tally options live
        av = self.model.activeView

        # reset form layout
        for i in reversed(range(self.tallySelectorLayout.count())):
            self.tallySelectorLayout.itemAt(i).widget().setParent(None)

        # always re-add the tally selector to the layout
        self.tallySelectorLayout.addRow(self.tallySelector)
        self.tallySelectorLayout.addRow(HorizontalLine())

        if tally_label is None or tally_label == "None" or tally_label == "":
            av.selectedTally = None
            self.score_map = None
            self.nuclide_map = None
            self.filter_map = None
            av.tallyValue = "Mean"
        else:
            # get the tally
            tally = self.model.statepoint.tallies[av.selectedTally]

            # populate filters
            filter_types = {type(f) for f in tally.filters}
            spatial_filters = bool(filter_types.intersection(_SPATIAL_FILTERS))

            if not spatial_filters:
                self.filter_description = QLabel("(No Spatial Filters)")
                self.tallySelectorLayout.addRow(self.filter_description)

            self._createFilterTree(spatial_filters)

            self.tallySelectorLayout.addRow(self.treeExpander)
            self.tallySelectorLayout.addRow(HorizontalLine())

            # value selection
            self.tallySelectorLayout.addRow(QLabel("Value:"))
            self.valueBox = QComboBox(self)
            self.values = tuple(_TALLY_VALUES.keys())
            for value in self.values:
                self.valueBox.addItem(value)
            self.tallySelectorLayout.addRow(self.valueBox)
            self.valueBox.currentTextChanged[str].connect(
                self.main_window.editTallyValue)
            self.updateTallyValue()

            if not spatial_filters:
                self.valueBox.setEnabled(False)
                self.valueBox.setToolTip(
                    "Only tallies with spatial filters are viewable.")

            # scores
            self.score_map = {}
            self.scoresListWidget.clear()

            for score in tally.scores:
                ql = QListWidgetItem()
                ql.setText(score)
                ql.setCheckState(QtCore.Qt.Unchecked)
                if not spatial_filters:
                    ql.setFlags(QtCore.Qt.ItemIsUserCheckable)
                else:
                    ql.setFlags(ql.flags() | QtCore.Qt.ItemIsUserCheckable)
                    ql.setFlags(ql.flags() & ~QtCore.Qt.ItemIsSelectable)
                self.score_map[score] = ql
                self.scoresListWidget.addItem(ql)

            # select the first score item by default
            for item in self.score_map.values():
                item.setCheckState(QtCore.Qt.Checked)
                break
            self.updateScores()

            self.scoresGroupBoxLayout = QVBoxLayout()
            self.scoresGroupBoxLayout.addWidget(self.scoresListWidget)
            self.scoresGroupBox = Expander(
                "Scores:", layout=self.scoresGroupBoxLayout)
            self.tallySelectorLayout.addRow(self.scoresGroupBox)

            # nuclides
            self.nuclide_map = {}
            self.nuclide_map.clear()
            self.nuclidesListWidget.clear()

            sorted_nuclides = sorted(tally.nuclides)
            # always put total at the top
            if 'total' in sorted_nuclides:
                idx = sorted_nuclides.index('total')
                sorted_nuclides.insert(0, sorted_nuclides.pop(idx))

            for nuclide in sorted_nuclides:
                ql = QListWidgetItem()
                ql.setText(nuclide.capitalize())
                ql.setCheckState(QtCore.Qt.Unchecked)
                if not spatial_filters:
                    ql.setFlags(QtCore.Qt.ItemIsUserCheckable)
                else:
                    ql.setFlags(ql.flags() | QtCore.Qt.ItemIsUserCheckable)
                    ql.setFlags(ql.flags() & ~QtCore.Qt.ItemIsSelectable)
                self.nuclide_map[nuclide] = ql
                self.nuclidesListWidget.addItem(ql)

            # select the first nuclide item by default
            for item in self.nuclide_map.values():
                item.setCheckState(QtCore.Qt.Checked)
                break
            self.updateNuclides()

            self.nuclidesGroupBoxLayout = QVBoxLayout()
            self.nuclidesGroupBoxLayout.addWidget(self.nuclidesListWidget)
            self.nuclidesGroupBox = Expander(
                "Nuclides:", layout=self.nuclidesGroupBoxLayout)
            self.tallySelectorLayout.addRow(self.nuclidesGroupBox)

    def updateMinMax(self):
        self.tallyColorForm.updateMinMax()

    def updateTallyValue(self):
        cv = self.model.currentView
        idx = self.valueBox.findText(cv.tallyValue)
        self.valueBox.setCurrentIndex(idx)

    def updateSelectedTally(self):
        cv = self.model.currentView
        idx = 0
        if cv.selectedTally:
            idx = self.tallySelector.findData(cv.selectedTally)
        self.tallySelector.setCurrentIndex(idx)

    def updateFilters(self):
        # if the filters header is checked, uncheck all bins and return
        applied_filters = defaultdict(tuple)
        for f, f_item in self.filter_map.items():
            if type(f) == openmc.MeshFilter:
                continue

            filter_checked = f_item.checkState(0)
            if filter_checked == QtCore.Qt.Unchecked:
                for i in range(f_item.childCount()):
                    bin_item = f_item.child(i)
                    bin_item.setCheckState(0, QtCore.Qt.Unchecked)
                applied_filters[f] = tuple()
            elif filter_checked == QtCore.Qt.Checked:
                if isinstance(f, openmc.EnergyFunctionFilter):
                    applied_filters[f] = (0,)
                else:
                    for i in range(f_item.childCount()):
                        bin_item = f_item.child(i)
                        bin_item.setCheckState(0, QtCore.Qt.Checked)
                    applied_filters[f] = tuple(range(f_item.childCount()))
            elif filter_checked == QtCore.Qt.PartiallyChecked:
                selected_bins = []
                if isinstance(f, openmc.EnergyFunctionFilter):
                    bins = [0]
                else:
                    bins = f.bins
                for idx, b in enumerate(bins):
                    b = b if not isinstance(b, Iterable) else tuple(b)
                    bin_checked = self.bin_map[(f, b)].checkState(0)
                    if bin_checked == QtCore.Qt.Checked:
                        selected_bins.append(idx)
                applied_filters[f] = tuple(selected_bins)

        self.model.appliedFilters = applied_filters

    def updateScores(self):
        applied_scores = []
        for score, score_box in self.score_map.items():
            if score_box.checkState() == QtCore.Qt.CheckState.Checked:
                applied_scores.append(score)
        self.model.appliedScores = tuple(applied_scores)

        with QtCore.QSignalBlocker(self.scoresListWidget):
            if not applied_scores:
                # if no scores are selected, enable all scores again
                for score, score_box in self.score_map.items():
                    score_box.setFlags(QtCore.Qt.ItemIsUserCheckable |
                                       QtCore.Qt.ItemIsEnabled |
                                       QtCore.Qt.ItemIsSelectable)
            else:
                # get units of applied scores
                selected_units = _SCORE_UNITS.get(
                    applied_scores[0], _REACTION_UNITS)
                # disable scores with incompatible units
                for score, score_box in self.score_map.items():
                    sunits = _SCORE_UNITS.get(score, _REACTION_UNITS)
                    if sunits != selected_units:
                        score_box.setFlags(QtCore.Qt.ItemIsUserCheckable)
                        score_box.setToolTip(
                            "Score is incompatible with currently selected scores")
                    else:
                        score_box.setFlags(score_box.flags() |
                                        QtCore.Qt.ItemIsUserCheckable)
                        score_box.setFlags(score_box.flags() &
                                        ~QtCore.Qt.ItemIsSelectable)

    def updateNuclides(self):
        applied_nuclides = []
        for nuclide, nuclide_box in self.nuclide_map.items():
            if nuclide_box.checkState() == QtCore.Qt.CheckState.Checked:
                applied_nuclides.append(nuclide)
        self.model.appliedNuclides = tuple(applied_nuclides)

        if 'total' in applied_nuclides:
            self.model.appliedNuclides = ('total',)
            for nuclide, nuclide_box in self.nuclide_map.items():
                if nuclide != 'total':
                    nuclide_box.setFlags(QtCore.Qt.ItemIsUserCheckable)
                    nuclide_box.setToolTip(
                        "De-select 'total' to enable other nuclides")
        elif not applied_nuclides:
            # if no nuclides are selected, enable all nuclides again
            for nuclide, nuclide_box in self.nuclide_map.items():
                empty_item = QListWidgetItem()
                nuclide_box.setFlags(empty_item.flags() |
                                     QtCore.Qt.ItemIsUserCheckable)
                nuclide_box.setFlags(empty_item.flags() &
                                     ~QtCore.Qt.ItemIsSelectable)

    def updateModel(self):
        self.updateFilters()
        self.updateScores()
        self.updateNuclides()

    def update(self):

        # update the color form
        self.tallyColorForm.update()

        if self.model.statepoint:
            self.tallySelector.clear()
            self.tallySelector.setEnabled(True)
            self.tallySelector.addItem("None")
            for idx, tally in enumerate(self.model.statepoint.tallies.values()):
                if tally.name == "":
                    self.tallySelector.addItem(
                        f'Tally {tally.id}', userData=tally.id)
                else:
                    self.tallySelector.addItem(
                        f'Tally {tally.id} "{tally.name}"', userData=tally.id)
                self.tally_map[idx] = tally
            self.updateSelectedTally()
            self.updateMinMax()
        else:
            self.tallySelector.clear()
            self.tallySelector.setDisabled(True)


class ColorForm(QWidget):
    """
    Class for handling a field with a colormap, alpha, and visibility

    Attributes
    ----------

    model : PlotModel
        The model instance used when updating information on the form.
    colormapBox : QComboBox
        Holds the string of the matplotlib colorbar being used
    visibilityBox : QCheckBox
        Indicator for whether or not the field should be visible
    alphaBox : QDoubleSpinBox
        Holds the alpha value for the displayed field data
    colormapBox : QComboBox
        Selector for colormap
    dataIndicatorCheckBox : QCheckBox
        Inidcates whether or not the data indicator will appear on the colorbar
    userMinMaxBox : QCheckBox
        Indicates whether or not the user defined values in the min and max
        will be used to set the bounds of the colorbar.
    maxBox : ScientificDoubleSpinBox
        Max value of the colorbar. If the userMinMaxBox is checked, this will be
        the user's input. If the userMinMaxBox is not checked, this box will
        hold the max value of the visible data.
    minBox : ScientificDoubleSpinBox
        Min value of the colorbar. If the userMinMaxBox is checked, this will be
        the user's input. If the userMinMaxBox is not checked, this box will
        hold the max value of the visible data.
    scaleBox : QCheckBox
        Indicates whether or not the data is displayed on a log or linear
        scale
    maskZeroBox : QCheckBox
        Indicates whether or not values equal to zero are displayed
    clipDataBox : QCheckBox
        Indicates whether or not values outside the min/max are displayed
    contoursBox :  QCheckBox
        Inidicates whether or not data is displayed as contours
    contourLevelsLine : QLineEdit
        Controls the contours of the data. If this line contains a single
        integer, that number of levels is used to display the data. If a
        comma-separated set of values is entered, those values will be used as
        levels in the contour plot.
    """

    def __init__(self, model, main_window, field, colormaps=None):
        super().__init__()

        self.model = model
        self.main_window = main_window
        self.field = field

        self.layout = QFormLayout()

        # Visibility check box
        self.visibilityBox = QCheckBox()
        visible_connector = partial(main_window.toggleTallyVisibility)
        self.visibilityBox.stateChanged.connect(visible_connector)

        # Alpha value
        self.alphaBox = QDoubleSpinBox()
        self.alphaBox.setDecimals(2)
        self.alphaBox.setRange(0, 1)
        self.alphaBox.setSingleStep(0.05)
        alpha_connector = partial(main_window.editTallyAlpha)
        self.alphaBox.valueChanged.connect(alpha_connector)

        # Color map selector
        self.colormapBox = QComboBox()
        if colormaps is None:
            colormaps = sorted(
                m for m in plt.colormaps() if not m.endswith("_r"))
        for colormap in colormaps:
            self.colormapBox.addItem(colormap)
        cmap_connector = partial(main_window.editTallyDataColormap)
        self.colormapBox.currentTextChanged[str].connect(cmap_connector)

        # Color map reverse
        self.reverseCmapBox = QCheckBox()
        reverse_connector = partial(main_window.toggleReverseCmap)
        self.reverseCmapBox.stateChanged.connect(reverse_connector)

        # Data indicator line check box
        self.dataIndicatorCheckBox = QCheckBox()
        data_indicator_connector = partial(
            main_window.toggleTallyDataIndicator)
        self.dataIndicatorCheckBox.stateChanged.connect(
            data_indicator_connector)

        # User specified min/max check box
        self.userMinMaxBox = QCheckBox()
        minmax_connector = partial(main_window.toggleTallyDataUserMinMax)
        self.userMinMaxBox.stateChanged.connect(minmax_connector)

        # Data min spin box
        self.minBox = ScientificDoubleSpinBox()
        self.minBox.setMinimum(0.0)
        min_connector = partial(main_window.editTallyDataMin)
        self.minBox.valueChanged.connect(min_connector)

        # Data max spin box
        self.maxBox = ScientificDoubleSpinBox()
        self.maxBox.setMinimum(0.0)
        max_connector = partial(main_window.editTallyDataMax)
        self.maxBox.valueChanged.connect(max_connector)

        # Linear/Log scaling check box
        self.scaleBox = QCheckBox()
        scale_connector = partial(main_window.toggleTallyLogScale)
        self.scaleBox.stateChanged.connect(scale_connector)

        # Masking of zero values check box
        self.maskZeroBox = QCheckBox()
        zero_connector = partial(main_window.toggleTallyMaskZero)
        self.maskZeroBox.stateChanged.connect(zero_connector)

        # Volume normalization check box
        self.volumeNormBox = QCheckBox()
        volume_connector = partial(main_window.toggleTallyVolumeNorm)
        self.volumeNormBox.stateChanged.connect(volume_connector)

        # Clip data to min/max check box
        self.clipDataBox = QCheckBox()
        clip_connector = partial(main_window.toggleTallyDataClip)
        self.clipDataBox.stateChanged.connect(clip_connector)

        # Display data as contour plot check box
        self.contoursBox = QCheckBox()
        self.contoursBox.stateChanged.connect(main_window.toggleTallyContours)
        self.contourLevelsLine = QLineEdit()
        self.contourLevelsLine.textChanged.connect(
            main_window.editTallyContourLevels)

        # Organize widgets on layout
        self.layout.addRow("Visible:", self.visibilityBox)
        self.layout.addRow("Alpha: ", self.alphaBox)
        self.layout.addRow("Colormap: ", self.colormapBox)
        self.layout.addRow("Reverse colormap: ", self.reverseCmapBox)
        self.layout.addRow("Data Indicator: ", self.dataIndicatorCheckBox)
        self.layout.addRow("Custom Min/Max: ", self.userMinMaxBox)
        self.layout.addRow("Min: ", self.minBox)
        self.layout.addRow("Max: ", self.maxBox)
        self.layout.addRow("Log Scale: ", self.scaleBox)
        self.layout.addRow("Clip Data: ", self.clipDataBox)
        self.layout.addRow("Mask Zeros: ", self.maskZeroBox)
        self.layout.addRow("Volume normalize: ", self.volumeNormBox)
        self.layout.addRow("Contours: ", self.contoursBox)
        self.layout.addRow("Contour Levels:", self.contourLevelsLine)
        self.setLayout(self.layout)

    def updateTallyContours(self):
        cv = self.model.currentView
        self.contoursBox.setChecked(cv.tallyContours)
        self.contourLevelsLine.setText(cv.tallyContourLevels)

    def updateDataIndicator(self):
        cv = self.model.currentView
        self.dataIndicatorCheckBox.setChecked(cv.tallyDataIndicator)

    def setMinMaxEnabled(self, enable):
        enable = bool(enable)
        self.minBox.setEnabled(enable)
        self.maxBox.setEnabled(enable)

    def updateMinMax(self):
        cv = self.model.currentView
        self.minBox.setValue(cv.tallyDataMin)
        self.maxBox.setValue(cv.tallyDataMax)
        self.setMinMaxEnabled(cv.tallyDataUserMinMax)

    def updateTallyVisibility(self):
        cv = self.model.currentView
        self.visibilityBox.setChecked(cv.tallyDataVisible)

    def updateMaskZeros(self):
        cv = self.model.currentView
        self.maskZeroBox.setChecked(cv.tallyMaskZeroValues)

    def updateVolumeNorm(self):
        cv = self.model.currentView
        self.volumeNormBox.setChecked(cv.tallyVolumeNorm)

    def updateDataClip(self):
        cv = self.model.currentView
        self.clipDataBox.setChecked(cv.clipTallyData)

    def update(self):
        cv = self.model.currentView

        # set colormap value in selector
        cmap = cv.tallyDataColormap
        idx = self.colormapBox.findText(cmap, QtCore.Qt.MatchFixedString)
        self.colormapBox.setCurrentIndex(idx)

        self.alphaBox.setValue(cv.tallyDataAlpha)
        self.visibilityBox.setChecked(cv.tallyDataVisible)
        self.userMinMaxBox.setChecked(cv.tallyDataUserMinMax)
        self.scaleBox.setChecked(cv.tallyDataLogScale)

        self.updateMinMax()
        self.updateMaskZeros()
        self.updateVolumeNorm()
        self.updateDataClip()
        self.updateDataIndicator()
        self.updateTallyContours()
