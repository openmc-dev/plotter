from collections import Iterable, defaultdict
from functools import partial
import itertools


from plot_colors import rgb_normalize, invert_rgb
from plotmodel import DomainDelegate
from plotmodel import _NOT_FOUND, _VOID_REGION, _OVERLAP, _MODEL_PROPERTIES

from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
                               QApplication, QGroupBox, QFormLayout, QLabel,
                               QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                               QSizePolicy, QSpacerItem, QMessageBox, QMainWindow, QCheckBox,
                               QRubberBand, QMenu, QAction, QMenuBar,
                               QFileDialog, QDialog, QTabWidget, QGridLayout,
                               QToolButton, QColorDialog, QFrame, QDockWidget,
                               QTableView, QItemDelegate, QHeaderView, QSlider,
                               QTextEdit, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem)
import matplotlib.pyplot as plt
from matplotlib.backends.qt_compat import is_pyqt5
from matplotlib.figure import Figure
from matplotlib import image as mpimage
from matplotlib import lines as mlines
from matplotlib import cm as mcolormaps
from matplotlib.colors import SymLogNorm, NoNorm
from matplotlib.transforms import Bbox

import openmc

import numpy as np

if is_pyqt5():
    from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
else:
    from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)

from docks import TallyDock, OptionsDock, score_units
from common_widgets import HorizontalLine


class PlotImage(FigureCanvas):

    def __init__(self, model, parent, main):

        self.figure = Figure(dpi=main.logicalDpiX())
        super().__init__(self.figure)

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

        self.colorbar = None
        self.data_indicator = None
        self.image = None

        self._supported_spatial_filters = (openmc.filter.CellFilter,
                                           openmc.filter.UniverseFilter,
                                           openmc.filter.MaterialFilter,
                                           openmc.filter.MeshFilter)

        self.menu = QMenu(self)

    def enterEvent(self, event):
        self.setCursor(QtCore.Qt.CrossCursor)
        self.mw.coord_label.show()

    def leaveEvent(self, event):
        self.mw.coord_label.hide()
        self.mw.statusBar().showMessage("")

    def mousePressEvent(self, event):
        self.mw.coord_label.hide()
        position = event.pos()
        # Set rubber band absolute and relative position
        self.band_origin = position
        self.x_plot_origin, self.y_plot_origin = self.getPlotCoords(position)

        # Create rubber band
        self.rubber_band.setGeometry(QtCore.QRect(self.band_origin,
                                                  QtCore.QSize()))

    def getPlotCoords(self, pos):
        x, y = self.mouseEventCoords(pos)

        # get the normalized axis coordinates from the event display units
        transform = self.ax.transAxes.inverted()
        xPlotCoord, yPlotCoord = transform.transform((x, y))
        # flip the y-axis (its zero is in the upper left)

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

    def _resize(self):
        z = self.mw.zoom / 100.0
        # manage scroll bars
        if z <= 1.0:
            self.parent.verticalScrollBar().hide()
            self.parent.horizontalScrollBar().hide()
            self.parent.cornerWidget().hide()
            self.parent.verticalScrollBar().setEnabled(False)
            self.parent.horizontalScrollBar().setEnabled(False)
        else:
            self.parent.verticalScrollBar().show()
            self.parent.horizontalScrollBar().show()
            self.parent.cornerWidget().show()
            self.parent.verticalScrollBar().setEnabled(True)
            self.parent.horizontalScrollBar().setEnabled(True)

        # resize plot
        self.resize(self.parent.width() * z,
                    self.parent.height() * z)

    def getDataIndices(self, event):
        cv = self.model.currentView

        x, y = self.mouseEventCoords(event.pos())

        # get origin in axes coordinates
        x0, y0 = self.ax.transAxes.transform((0.0, 0.0))

        # get the extents of the axes box in axes coordinates
        bbox = self.ax.get_window_extent().transformed(
            self.figure.dpi_scale_trans.inverted())
        # get dimensions and scale using dpi
        width, height = bbox.width, bbox.height
        width *= self.figure.dpi
        height *= self.figure.dpi

        # use factor to get proper x,y position in pixels
        factor = (width/cv.h_res, height/cv.v_res)
        xPos = int((x - x0 + 0.01) / factor[0])
        # flip y-axis
        yPos = cv.v_res - int((y - y0 + 0.01) / factor[1])

        return xPos, yPos

    def getTallyIndices(self, event):

        xPos, yPos = self.getPlotCoords(event.pos())

        ext = self.model.tally_extents

        x0 = ext[0]
        y0 = ext[2]

        v_res, h_res = self.model.tally_data.shape

        dx = (ext[1] - ext[0]) / h_res
        dy = (ext[3] - ext[2]) / v_res

        i = int((xPos - x0) // dx)
        j = v_res - int((yPos - y0) // dy) - 1

        return i, j

    def getTallyInfo(self, event):
        cv = self.model. currentView

        xPos, yPos = self.getTallyIndices(event)

        if self.model.tally_data is None:
            return -1, None

        if not self.model.selectedTally or not cv.tallyDataVisible:
            return -1, None

        tally_id = self.model.selectedTally

        # don't look up mesh filter data (for now)
        tally = self.model.statepoint.tallies[tally_id]
        filters = tally.filters

        # check that the position is in the axes view
        v_res, h_res = self.model.tally_data.shape
        if 0 <= yPos < v_res and 0 <= xPos < h_res:
            value = self.model.tally_data[yPos][xPos]
        else:
            value = None

        return tally_id, value

    def getIDinfo(self, event):

        xPos, yPos = self.getDataIndices(event)

        # check that the position is in the axes view
        if 0 <= yPos < self.model.currentView.v_res \
           and 0 <= xPos and xPos < self.model.currentView.h_res:
            id = self.model.ids[yPos][xPos]
            temp = "{:g}".format(self.model.properties[yPos][xPos][0])
            density = "{:g}".format(self.model.properties[yPos][xPos][1])
        else:
            id = _NOT_FOUND
            density = str(_NOT_FOUND)
            temp = str(_NOT_FOUND)

        if self.model.currentView.colorby == 'cell':
            domain = self.model.activeView.cells
            domain_kind = 'Cell'
        elif self.model.currentView.colorby == 'temperature':
            domain = self.model.activeView.materials
            domain_kind = 'Temperature'
        elif self.model.currentView.colorby == 'density':
            domain = self.model.activeView.materials
            domain_kind = 'Density'
        else:
            domain = self.model.activeView.materials
            domain_kind = 'Material'

        properties = {'density': density,
                      'temperature': temp}

        return id, properties, domain, domain_kind

    def mouseDoubleClickEvent(self, event):
        xCenter, yCenter = self.getPlotCoords(event.pos())
        self.mw.editPlotOrigin(xCenter, yCenter, apply=True)

    def mouseMoveEvent(self, event):

        # Show Cursor position relative to plot in status bar
        xPlotPos, yPlotPos = self.getPlotCoords(event.pos())

        # Show Cell/Material ID, Name in status bar
        id, properties, domain, domain_kind = self.getIDinfo(event)

        domainInfo = ""
        tallyInfo = ""

        if self.parent.underMouse():

            if domain_kind.lower() in _MODEL_PROPERTIES:
                line_val = float(properties[domain_kind.lower()])
                line_val = max(line_val, 0.0)
                self.updateDataIndicatorValue(line_val)
                domain_kind = 'Material'

            temperature = properties['temperature']
            density = properties['density']

            if id == _VOID_REGION:
                domainInfo = ("VOID")
            elif id == _OVERLAP:
                domainInfo = ("OVERLAP")
            elif id != _NOT_FOUND and domain[id].name:
                domainInfo = ("{} {}: \"{}\"\t Density: {} g/cc\t"
                              "Temperature: {} K".format(domain_kind,
                                                         id,
                                                         domain[id].name,
                                                         density,
                                                         temperature))
            elif id != _NOT_FOUND:
                domainInfo = ("{} {}\t Density: {} g/cc\t"
                              "Temperature: {} K".format(domain_kind,
                                                         id,
                                                         density,
                                                         temperature))
            else:
                domainInfo = ""

            if self.model.selectedTally:
                tid, value = self.getTallyInfo(event)
                if value is not None:
                    tallyInfo = "Tally {}: {:.5E}".format(tid, value)
        else:
            self.updateDataIndicatorValue(0.0)

        self.mw.statusBar().showMessage(" " + domainInfo + "      " + tallyInfo)

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
            # Zoom in
            else:
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

        self.mw.undoAction.setText('&Undo ({})'.format(len(self.model.previousViews)))
        self.mw.redoAction.setText('&Redo ({})'.format(len(self.model.subsequentViews)))

        id, properties, domain, domain_kind = self.getIDinfo(event)

        cv = self.model.currentView

        # always provide undo option
        self.menu.addSeparator()
        self.menu.addAction(self.mw.undoAction)
        self.menu.addAction(self.mw.redoAction)
        self.menu.addSeparator()

        if int(id) not in (_NOT_FOUND, _OVERLAP) and \
           cv.colorby not in _MODEL_PROPERTIES:

            # Domain ID
            if domain[id].name:
                domainID = self.menu.addAction("{} {}: \"{}\"".format(domain_kind, id, domain[id].name))
            else:
                domainID = self.menu.addAction("{} {}".format(domain_kind, id))

            self.menu.addSeparator()

            colorAction = self.menu.addAction('Edit {} Color...'.format(domain_kind))
            colorAction.setDisabled(cv.highlighting)
            colorAction.setToolTip('Edit {} color'.format(domain_kind))
            colorAction.setStatusTip('Edit {} color'.format(domain_kind))
            domain_color_connector = partial(self.mw.editDomainColor,
                                             domain_kind,
                                             id)
            colorAction.triggered.connect(domain_color_connector)

            maskAction = self.menu.addAction('Mask {}'.format(domain_kind))
            maskAction.setCheckable(True)
            maskAction.setChecked(domain[id].masked)
            maskAction.setDisabled(not cv.masking)
            maskAction.setToolTip('Toggle {} mask'.format(domain_kind))
            maskAction.setStatusTip('Toggle {} mask'.format(domain_kind))
            mask_connector = partial(self.mw.toggleDomainMask,
                                     kind=domain_kind,
                                     id=id)
            maskAction.toggled.connect(mask_connector)

            highlightAction = self.menu.addAction('Highlight {}'.format(domain_kind))
            highlightAction.setCheckable(True)
            highlightAction.setChecked(domain[id].highlight)
            highlightAction.setDisabled(not cv.highlighting)
            highlightAction.setToolTip('Toggle {} highlight'.format(domain_kind))
            highlightAction.setStatusTip('Toggle {} highlight'.format(domain_kind))
            highlight_connector = partial(self.mw.toggleDomainHighlight,
                                          kind=domain_kind,
                                          id=id)
            highlightAction.toggled.connect(highlight_connector)

        else:
            self.menu.addAction(self.mw.undoAction)
            self.menu.addAction(self.mw.redoAction)

            if cv.colorby not in _MODEL_PROPERTIES:
                self.menu.addSeparator()
                if int(id) == _NOT_FOUND:
                    bgColorAction = self.menu.addAction('Edit Background Color...')
                    bgColorAction.setToolTip('Edit background color')
                    bgColorAction.setStatusTip('Edit plot background color')
                    connector = partial(self.mw.editBackgroundColor, apply=True)
                    bgColorAction.triggered.connect(connector)
                elif int(id) == _OVERLAP:
                    olapColorAction = self.menu.addAction('Edit Overlap Color...')
                    olapColorAction.setToolTip('Edit overlap color')
                    olapColorAction.setStatusTip('Edit plot overlap color')
                    connector = partial(self.mw.editOverlapColor, apply=True)
                    olapColorAction.triggered.connect(connector)

        self.menu.addSeparator()
        self.menu.addAction(self.mw.saveImageAction)
        self.menu.addAction(self.mw.saveViewAction)
        self.menu.addAction(self.mw.openAction)
        self.menu.addSeparator()
        self.menu.addMenu(self.mw.basisMenu)
        self.menu.addMenu(self.mw.colorbyMenu)
        self.menu.addSeparator()
        if domain_kind.lower() not in ('density', 'temperature'):
            self.menu.addAction(self.mw.maskingAction)
            self.menu.addAction(self.mw.highlightingAct)
            self.menu.addAction(self.mw.overlapAct)
            self.menu.addSeparator()
        self.menu.addAction(self.mw.dockAction)

        self.mw.maskingAction.setChecked(cv.masking)
        self.mw.highlightingAct.setChecked(cv.highlighting)
        self.mw.overlapAct.setChecked(cv.color_overlaps)

        if self.mw.dock.isVisible():
            self.mw.dockAction.setText('Hide &Dock')
        else:
            self.mw.dockAction.setText('Show &Dock')

        self.menu.exec_(event.globalPos())

    def generatePixmap(self):
        self.model.generatePlot()
        self.updatePixmap()

    def updatePixmap(self):

        # clear out figure
        self.figure.clear()

        cv = self.model.currentView
        # set figure bg color to match window
        window_bg = self.parent.palette().color(QtGui.QPalette.Background)
        self.figure.patch.set_facecolor(rgb_normalize(window_bg.getRgb()))

        # set data extents for automatic reporting of pointer location
        data_bounds = [cv.origin[self.mw.xBasis] - cv.width/2.,
                       cv.origin[self.mw.xBasis] + cv.width/2.,
                       cv.origin[self.mw.yBasis] - cv.height/2.,
                       cv.origin[self.mw.yBasis] + cv.height/2.]

        # make sure we have an image to load
        if not hasattr(self.model, 'image'):
            self.model.generatePlot()

        alpha = cv.plotAlpha
        if not cv.plotVisibility:
            alpha = 0.0

        if cv.colorby in ('material', 'cell'):
            self.image = self.figure.subplots().imshow(self.model.image,
                                                       extent=data_bounds,
                                                       alpha=alpha)
        else:
            cmap = cv.colormaps[cv.colorby]
            if cv.colorby == 'temperature':
                idx = 0
                cmap_label = "Temperature (K)"
            else:
                idx = 1
                cmap_label = "Density (g/cc)"

            norm = SymLogNorm(1E-2) if cv.color_scale_log[cv.colorby] else None
            data = self.model.properties[:, :, idx]
            self.image = self.figure.subplots().imshow(data,
                                                       cmap=cmap,
                                                       norm=norm,
                                                       extent=data_bounds,
                                                       alpha=cv.plotAlpha)

            # add colorbar
            self.colorbar = self.figure.colorbar(self.image,
                                                 anchor=(1.0, 0.0))
            self.colorbar.set_label(cmap_label,
                                    rotation=-90,
                                    va='bottom',
                                    ha='right')
            # draw line on colorbar
            dl = self.colorbar.ax.dataLim.get_points()
            self.data_indicator = mlines.Line2D(dl[:][0],
                                                [0.0, 0.0],
                                                linewidth=3.,
                                                color='blue',
                                                clip_on=True)
            self.colorbar.ax.add_line(self.data_indicator)
            self.colorbar.ax.margins(0.0 ,0.0)
            self.updateDataIndicatorVisibility()
            self.updateColorMinMax(cv.colorby)

        self.ax = self.figure.axes[0]
        self.ax.margins(0.0, 0.0)

        # set axis labels
        axis_label_str = "{} (cm)"
        self.ax.set_xlabel(axis_label_str.format(cv.basis[0]))
        self.ax.set_ylabel(axis_label_str.format(cv.basis[1]))

        # draw tally
        tally_selected =  self.model.selectedTally is not None
        tally_visible = self.model.currentView.tallyDataVisible
        nuclides_and_scores_selected = bool(self.model.appliedNuclides)
        nuclides_and_scores_selected &= bool(self.model.appliedScores)

        if tally_selected and tally_visible and not nuclides_and_scores_selected:
            return "No tallies or scores selected!"

        if tally_selected and tally_visible and nuclides_and_scores_selected:
            image_data, extents, data_min, data_max, units = self.create_tally_image(self.model.selectedTally,
                                                                            self.model.appliedScores,
                                                                            self.model.appliedNuclides)

            if image_data is None:
                self.draw()
                return "Done"

            if extents is None:
                extents = data_bounds

            self.model.tally_data = image_data
            self.model.tally_extents = extents if extents is not None else data_bounds

            norm = SymLogNorm(1E-2) if cv.tallyDataLogScale else None

            self.tally_image = self.ax.imshow(image_data,
                                              alpha = cv.tallyDataAlpha,
                                              cmap = cv.tallyDataColormap,
                                              norm = norm,
                                              extent=extents)
            # add colorbar
            self.tally_colorbar = self.figure.colorbar(self.tally_image,
                                                       anchor=(1.0, 0.0))


            if not cv.tallyDataUserMinMax:
                cv.tallyDataMin = data_min
                cv.tallyDataMax = data_max
            else:
                data_min = cv.tallyDataMin
                data_max = cv.tallyDataMax

            self.mw.updateTallyMinMax()

            self.tally_colorbar.mappable.set_clim(data_min, data_max)
            self.tally_colorbar.set_label(units,
                                          rotation=-90,
                                          va='bottom',
                                          ha='right')

        if cv.colorby in ('material', 'cell') and cv.outlines:
            if cv.colorby == 'material':
                levels = len(cv.materials)
            else:
                levels = len(cv.cells)
            self.ax.contour(self.model.mat_ids[::-1],
                            colors='k',
                            levels=levels,
                            extent=data_bounds)

        # always make sure the data bounds are set correctly
        self.ax.set_xbound(data_bounds[0], data_bounds[1])
        self.ax.set_ybound(data_bounds[2], data_bounds[3])
        self.ax.dataLim.x0 = data_bounds[0]
        self.ax.dataLim.x1 = data_bounds[1]
        self.ax.dataLim.y0 = data_bounds[2]
        self.ax.dataLim.y1 = data_bounds[3]

        self.draw()
        return "Done"

    def _create_tally_domain_image(self, tally, scores, nuclides):
        # data resources used throughout
        cv = self.model.currentView
        sp = self.model.statepoint

        data = tally.get_reshaped_data()
        data_out = np.full(self.model.ids.shape, -1.0)

        # data structure for tracking which spatial
        # filter bins are enabled
        spatial_filter_bins = defaultdict(list)

        for filter_idx, filter in enumerate(tally.filters):
            filter_check_state = self.mw.tallyDock.filter_map[filter].checkState(0)

            if filter_check_state != QtCore.Qt.Unchecked:

                selected_bins = []
                for idx, bin in enumerate(filter.bins):
                    bin = bin if not hasattr(bin, '__iter__') else tuple(bin)
                    bin_check_state = self.mw.tallyDock.bin_map[(filter, bin)].checkState(0)
                    if bin_check_state == QtCore.Qt.Checked:
                        selected_bins.append(idx)

                if type(filter) in self._supported_spatial_filters:
                    spatial_filter_bins[filter] = selected_bins
                else:
                    data = data[np.array(selected_bins)].sum(axis=0)
            else:
                data[:,...] = 0.0
                data = data.sum(axis=0)

        # filter by selected scores
        selected_scores = []
        for idx, score in enumerate(tally.scores):
            if score in scores:
                selected_scores.append(idx)
        data = data[..., np.array(selected_scores)].sum(axis=-1)

        # filter by selected nuclides
        selected_nuclides = []
        for idx, nuclide in enumerate(tally.nuclides):
            if nuclide in nuclides:
                selected_nuclides.append(idx)
        data = data[..., np.array(selected_nuclides)].sum(axis=-1)

        # get data limits
        data_min = np.min(data)
        data_max = np.max(data)

        # for all combinations of spatial bins, create a mask
        # and set image data values
        spatial_filters = list(spatial_filter_bins.keys())
        spatial_bins = list(spatial_filter_bins.values())
        for bin_indices in itertools.product(*spatial_bins):

            # look up the tally value
            tally_val = data[bin_indices]
            if tally_val == 0.0:
                continue

            # generate a mask with the correct size
            mask = np.full(self.model.ids.shape, True, dtype=bool)

            for filter, bin_idx in zip(spatial_filters, bin_indices):
                bin= filter.bins[bin_idx]
                if isinstance(filter, openmc.Cell):
                    mask &= self.model.cell_ids == bin
                elif isinstance(filter, openmc.MaterialFilter):
                    mask &= self.model.mat_ids == bin
                elif isinstance(filter, openmc.UniverseFilter):
                    # get the statepoint summary
                    univ_cells = self.model.statepoint.universes[bin].cells
                    for cell in univ_cells:
                        mask &= self.model.cell_ids == cell

            # set image data values
            data_out[mask] = tally_val

        # mask out invalid values
        image_data = np.ma.masked_where(data_out < 0.0, data_out)

        return image_data, None, data_min, data_max

    def _create_tally_mesh_image(self, tally, scores, nuclides):
        # some variables used throughout
        cv = self.model.currentView
        sp = self.model.statepoint
        mesh = tally.find_filter(openmc.MeshFilter).mesh

        # start with reshaped data
        data = tally.get_reshaped_data()

        # determine basis indices
        if cv.basis == 'xy':
            h_ind = 0
            v_ind = 1
            ax = 2
        elif cv.basis == 'yz':
            h_ind = 1
            v_ind = 2
            ax = 0
        else:
            h_ind = 0
            v_ind = 2
            ax = 1

        # reduce data to the visible slice of the mesh values
        k = int((cv.origin[ax] - mesh.lower_left[ax]) // mesh.width[ax])

         # setup slice
        data_slice = [None, None, None]
        data_slice[h_ind] = slice(mesh.dimension[h_ind])
        data_slice[v_ind] = slice(mesh.dimension[v_ind])
        data_slice[ax] = k

        # move mesh axes to the end of the filters
        filter_idx = [ type(filter) for filter in tally.filters ].index(openmc.MeshFilter)
        data = np.moveaxis(data, filter_idx, -1)
        data = data.reshape(data.shape[:-1] + tuple(mesh.dimension))
        data = np.swapaxes(data, -3, -1)
        data = data[..., data_slice[0], data_slice[1], data_slice[2]]

        # sum over the rest of the tally filters
        for filter_idx, filter in enumerate(tally.filters):
            if type(filter) == openmc.MeshFilter:
                continue

            filter_check_state = self.mw.tallyDock.filter_map[filter].checkState(0)

            if filter_check_state != QtCore.Qt.Unchecked:
                selected_bins = []
                for idx, bin in enumerate(filter.bins):
                    if isinstance(bin, Iterable):
                        bin = tuple(bin)
                    # see if the bin is checked
                    bin_check_state = self.mw.tallyDock.bin_map[(filter, bin)].checkState(0)
                    if bin_check_state == QtCore.Qt.Checked:
                        selected_bins.append(idx)
                # sum filter data for the selected bins
                data = data[np.array(selected_bins)].sum(axis=0)
            else:
                # if the filter is completely unselected,
                # set all of it's data to zero and remove the axis
                data[:,...] = 0.0
                data = data.sum(axis=0)

        # filter by selected nuclides
        selected_nuclides = []
        for idx, nuclide in enumerate(tally.nuclides):
            if nuclide in nuclides:
                selected_nuclides.append(idx)
        data = data[np.array(selected_nuclides)].sum(axis=0)

        # filter by selected scores
        selected_scores = []
        for idx, score in enumerate(tally.scores):
            if score in scores:
                selected_scores.append(idx)
        data = data[np.array(selected_scores)].sum(axis=0)

        # get dataset's min/max
        data_min = np.min(data)
        data_max = np.max(data)

        # transpose data for reversed y-indexing
        image_data = data.transpose()

        # return data extents (in cm) for the tally
        extents = [mesh.lower_left[h_ind], mesh.upper_right[h_ind], mesh.lower_left[v_ind], mesh.upper_right[v_ind]]

        return image_data, extents, data_min, data_max

    def create_tally_image(self, tally_id, scores=[], nuclides=[]):

        cv = self.model.currentView

        tally = self.model.statepoint.tallies[tally_id]

        # check score units
        units = set()
        for score in scores:
            try:
                unit = score_units[score.lower()]
            except KeyError:
                msg_box = QMessageBox()
                msg_box.setText("Could not find unit for score '{}'".format(score))
                msg_box.setIcon(QMessageBox.Information)
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.exec_()
                return (None, None, None, None, None)

            units.add(unit)

        if len(units) != 1:
            msg_box = QMessageBox()
            unit_str = " ".join(units)
            msg = "The scores selected have incompatible units:\n"
            for unit in units:
                msg += "  - {}\n".format(unit)
            msg_box.setText(msg)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
            return (None, None, None, None, None)

        units_out = list(units)[0]

        if tally.contains_filter(openmc.MeshFilter):
            return self._create_tally_mesh_image(tally, scores, nuclides) + (units_out,)
        else:
            return self._create_tally_domain_image(tally, scores, nuclides) + (units_out,)

    def updateColorbarScale(self):
        self.updatePixmap()

    def updateDataIndicatorValue(self, y_val):
        cv = self.model.currentView

        if cv.colorby not in _MODEL_PROPERTIES or \
           not cv.data_indicator_enabled[cv.colorby]:
            return

        if self.data_indicator:
            data = self.data_indicator.get_data()
            # use norm to get axis value if log scale
            if cv.color_scale_log[cv.colorby]:
                y_val = self.image.norm(y_val)
            self.data_indicator.set_data([data[0], [y_val, y_val]])
            dl_color = invert_rgb(self.colorbar.get_cmap()(y_val), True)
            self.data_indicator.set_c(dl_color)
            self.draw()

    def updateDataIndicatorVisibility(self):
        cv = self.model.currentView
        if self.data_indicator and cv.colorby in _MODEL_PROPERTIES:
            val = cv.data_indicator_enabled[cv.colorby]
            self.data_indicator.set_visible(val)
            self.draw()

    def updateColorMap(self, colormap_name, property_type):
        if self.colorbar and property_type == self.model.activeView.colorby:
            self.colorbar.set_cmap(colormap_name)
            self.image.set_cmap(colormap_name)
            self.colorbar.draw_all()
            self.draw()

    def updateColorMinMax(self, property_type):
        av = self.model.activeView
        if self.colorbar and property_type == av.colorby:
            clim = av.getColorLimits(property_type)
            self.colorbar.mappable.set_clim(*clim)
            self.data_indicator.set_data(clim[:2],
                                         (0.0, 0.0))
            self.colorbar.draw_all()
            self.draw()

class ColorDialog(QDialog):

    def __init__(self, model, FM, parent=None):
        super().__init__(parent)

        self.setWindowTitle('Color Options')

        self.model = model
        self.FM = FM
        self.mw = parent

        self.createDialogLayout()

    def createDialogLayout(self):

        self.createGeneralTab()

        self.cellTable = self.createDomainTable(self.mw.cellsModel)
        self.matTable = self.createDomainTable(self.mw.materialsModel)
        self.tabs = {'cell': self.createDomainTab(self.cellTable),
                     'material': self.createDomainTab(self.matTable),
                     'temperature': self.createPropertyTab('temperature'),
                     'density': self.createPropertyTab('density')}

        self.tab_bar = QTabWidget()
        self.tab_bar.setMaximumHeight(800)
        self.tab_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tab_bar.addTab(self.generalTab, 'General')
        self.tab_bar.addTab(self.tabs['cell'], 'Cells')
        self.tab_bar.addTab(self.tabs['material'], 'Materials')
        self.tab_bar.addTab(self.tabs['temperature'], 'Temperature')
        self.tab_bar.addTab(self.tabs['density'], 'Density')

        self.createButtonBox()

        self.colorDialogLayout = QVBoxLayout()
        self.colorDialogLayout.addWidget(self.tab_bar)
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

        # Overlap plotting
        self.overlapCheck = QCheckBox('', self)
        overlap_connector = partial(self.mw.toggleOverlaps)
        self.overlapCheck.stateChanged.connect(overlap_connector)

        self.overlapColorButton = QPushButton()
        self.overlapColorButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.overlapColorButton.setFixedWidth(self.FM.width("XXXXXXXXXX"))
        self.overlapColorButton.setFixedHeight(self.FM.height() * 1.5)
        self.overlapColorButton.clicked.connect(self.mw.editOverlapColor)

        self.colorbyBox.currentTextChanged[str].connect(self.mw.editColorBy)

        self.colorResetButton = QPushButton("&Reset Colors")
        self.colorResetButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.colorResetButton.clicked.connect(self.mw.resetColors)

        formLayout = QFormLayout()
        formLayout.setAlignment(QtCore.Qt.AlignHCenter)
        formLayout.setFormAlignment(QtCore.Qt.AlignHCenter)
        formLayout.setLabelAlignment(QtCore.Qt.AlignLeft)

        formLayout.addRow('Masking:', self.maskingCheck)
        formLayout.addRow('Mask Color:', self.maskColorButton)
        formLayout.addRow(HorizontalLine())
        formLayout.addRow('Highlighting:', self.hlCheck)
        formLayout.addRow('Highlight Color:', self.hlColorButton)
        formLayout.addRow('Highlight Alpha:', self.alphaBox)
        formLayout.addRow('Highlight Seed:', self.seedBox)
        formLayout.addRow(HorizontalLine())
        formLayout.addRow('Background Color:          ', self.bgButton)
        formLayout.addRow(HorizontalLine())
        formLayout.addRow('Show Overlaps:', self.overlapCheck)
        formLayout.addRow('OVerlap Color:', self.overlapColorButton)
        formLayout.addRow(HorizontalLine())
        formLayout.addRow('Color Plot By:', self.colorbyBox)
        formLayout.addRow(self.colorResetButton, None)

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

    def createPropertyTab(self, property_kind):
        propertyTab = QWidget()
        propertyTab.property_kind = property_kind
        propertyTab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        propertyLayout = QVBoxLayout()

        propertyTab.minMaxCheckBox = QCheckBox()
        propertyTab.minMaxCheckBox.setCheckable(True)
        connector1 = partial(self.mw.toggleUserMinMax, property=property_kind)
        propertyTab.minMaxCheckBox.stateChanged.connect(connector1)

        propertyTab.minBox = QDoubleSpinBox(self)
        propertyTab.minBox.setMaximum(1E9)
        propertyTab.minBox.setMinimum(0)
        propertyTab.maxBox = QDoubleSpinBox(self)
        propertyTab.maxBox.setMaximum(1E9)
        propertyTab.maxBox.setMinimum(0)

        connector2 = partial(self.mw.editColorbarMin,
                             property_type=property_kind)
        propertyTab.minBox.valueChanged.connect(connector2)
        connector3 = partial(self.mw.editColorbarMax,
                             property_type=property_kind)
        propertyTab.maxBox.valueChanged.connect(connector3)

        propertyTab.colormapBox = QComboBox(self)
        cmaps = sorted(m for m in mcolormaps.datad if not m.endswith("_r"))
        for cmap in cmaps:
            propertyTab.colormapBox.addItem(cmap)

        connector = partial(self.mw.editColorMap, property_type=property_kind)

        propertyTab.colormapBox.currentTextChanged[str].connect(connector)

        propertyTab.dataIndicatorCheckBox = QCheckBox()
        propertyTab.dataIndicatorCheckBox.setCheckable(True)
        connector4 = partial(self.mw.toggleDataIndicatorCheckBox,
                             property=property_kind)
        propertyTab.dataIndicatorCheckBox.stateChanged.connect(connector4)

        propertyTab.colorBarScaleCheckBox = QCheckBox()
        propertyTab.colorBarScaleCheckBox.setCheckable(True)
        connector5 = partial(self.mw.toggleColorbarScale,
                             property=property_kind)
        propertyTab.colorBarScaleCheckBox.stateChanged.connect(connector5)

        formLayout = QFormLayout()
        formLayout.setAlignment(QtCore.Qt.AlignHCenter)
        formLayout.setFormAlignment(QtCore.Qt.AlignHCenter)
        formLayout.setLabelAlignment(QtCore.Qt.AlignLeft)

        formLayout.addRow('Colormap:', propertyTab.colormapBox)

        formLayout.addRow('Custom Min/Max', propertyTab.minMaxCheckBox)
        formLayout.addRow('Data Indicator', propertyTab.dataIndicatorCheckBox)
        formLayout.addRow('Log Scale', propertyTab.colorBarScaleCheckBox)
        formLayout.addRow(HorizontalLine())
        formLayout.addRow('Max: ', propertyTab.maxBox)
        formLayout.addRow('Min: ', propertyTab.minBox)

        propertyTab.setLayout(formLayout)

        return propertyTab

    def updateDataIndicatorVisibility(self):
        av = self.model.activeView
        for key, val in av.data_indicator_enabled.items():
            self.tabs[key].dataIndicatorCheckBox.setChecked(val)

    def updateColorMaps(self):
        cmaps = self.model.activeView.colormaps
        for key, val in cmaps.items():
            idx = self.tabs[key].colormapBox.findText(val,
                                                      QtCore.Qt.MatchFixedString)
            if idx >= 0:
                self.tabs[key].colormapBox.setCurrentIndex(idx)

    def updateColorMinMax(self):
        minmax = self.model.activeView.user_minmax
        for key, val in minmax.items():
            self.tabs[key].minBox.setValue(val[0])
            self.tabs[key].maxBox.setValue(val[1])
        custom_minmax = self.model.activeView.use_custom_minmax
        for key, val, in custom_minmax.items():
            self.tabs[key].minMaxCheckBox.setChecked(val)

    def updateColorbarScale(self):
        av = self.model.activeView
        for key, val in av.color_scale_log.items():
            self.tabs[key].colorBarScaleCheckBox.setChecked(val)

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
        self.updateColorMaps()
        self.updateColorMinMax()
        self.updateColorbarScale()
        self.updateDataIndicatorVisibility()
        self.updateHighlighting()
        self.updateHighlightColor()
        self.updateAlpha()
        self.updateSeed()
        self.updateBackgroundColor()
        self.updateColorBy()
        self.updateDomainTabs()
        self.updateOverlap()
        self.updateOverlapColor()

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
        style_values = "border-radius: 8px; background-color: rgb{}"
        self.maskColorButton.setStyleSheet(style_values.format(str(color)))

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
        style_values = "border-radius: 8px; background-color: rgb{}"
        self.hlColorButton.setStyleSheet(style_values.format(str(color)))

    def updateAlpha(self):
        self.alphaBox.setValue(self.model.activeView.highlightAlpha)

    def updateSeed(self):
        self.seedBox.setValue(self.model.activeView.highlightSeed)

    def updateBackgroundColor(self):
        color = self.model.activeView.plotBackground
        self.bgButton.setStyleSheet("border-radius: 8px;"
                                    "background-color: rgb%s" % (str(color)))

    def updateOverlapColor(self):
        color = self.model.activeView.overlap_color
        self.overlapColorButton.setStyleSheet("border-radius: 8px;"
                                              "background-color: rgb%s" % (str(color)))

    def updateOverlap(self):
        colorby = self.model.activeView.colorby
        overlap_val = self.model.activeView.color_overlaps
        if colorby in ('cell', 'material'):
            self.overlapCheck.setChecked(overlap_val)

    def updateColorBy(self):
        colorby = self.model.activeView.colorby
        self.colorbyBox.setCurrentText(colorby)
        self.overlapCheck.setEnabled(colorby in ("cell", "material"))

    def updateDomainTabs(self):
        self.cellTable.setModel(self.mw.cellsModel)
        self.matTable.setModel(self.mw.materialsModel)
