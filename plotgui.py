from functools import partial

from plot_colors import rgb_normalize, invert_rgb
from plotmodel import DomainDelegate
from plotmodel import _NOT_FOUND, _VOID_REGION, _OVERLAP, _MODEL_PROPERTIES

from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
                               QApplication, QGroupBox, QFormLayout, QLabel,
                               QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                               QSizePolicy, QSpacerItem, QMainWindow, QCheckBox,
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
import openmc
from openmc.filter import (UniverseFilter, MaterialFilter, CellFilter,
                           SurfaceFilter, MeshFilter, MeshSurfaceFilter)


import numpy as np

if is_pyqt5():
    from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
else:
    from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)


_SPATIAL_FILTERS = [UniverseFilter, MaterialFilter, CellFilter,
                    SurfaceFilter, MeshFilter, MeshSurfaceFilter]

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

    def getTallyInfo(self, event):
        cv = self.model. currentView

        xPos, yPos = self.getDataIndices(event)

        if self.model.tally_data is None:
            return -1, None

        if not self.model.selectedTally or not cv.tallyDataVisible:
            return -1, None

        tally_id = self.model.selectedTally

        return -1, None

        # check that the position is in the axes view
        if 0 <= yPos < self.model.currentView.v_res \
           and 0 <= xPos and xPos < self.model.currentView.h_res:
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

#        FigureCanvas.mouseDoubleClickEvent(self, event)

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

        if cv.colorby in ('material', 'cell'):
            self.image = self.figure.subplots().imshow(self.model.image,
                                                       extent=data_bounds,
                                                       alpha=cv.plotAlpha)
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
            image_data, data_min, data_max = self.create_tally_image(self.model.selectedTally,
                                                                     self.model.appliedScores,
                                                                     self.model.appliedNuclides)

            self.model.tally_data = image_data

            norm = SymLogNorm(1E-2) if cv.tallyDataLogScale else None
            self.tally_image = self.ax.imshow(image_data,
                                              alpha = cv.tallyDataAlpha,
                                              cmap = cv.tallyDataColormap,
                                              norm = norm,
                                              extent=data_bounds)
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
            self.tally_colorbar.set_label('Units',
                                          rotation=-90,
                                          va='bottom',
                                          ha='right')

        self.draw()

        return "Done"

    def create_tally_image(self, tally_id, scores=[], nuclides=[]):
        supported_spatial_filters = (openmc.filter.CellFilter,
                                     openmc.filter.UniverseFilter,
                                     openmc.filter.MaterialFilter,
                                     openmc.filter.MeshFilter)

        cv = self.model.currentView

        tally = self.model.statepoint.tallies[tally_id]
        tally_value = cv.tallyValue
        # convert tally value to OpenMC format
        tally_value = tally_value.lower().replace(".","").replace(" ", "_")

        # find a spatial filter
        for filter in tally.filters:
            if type(filter) in supported_spatial_filters:
                break

        filter_type = type(filter)

        if filter_type not in supported_spatial_filters:
            raise NotImplementedError("'{}' is not supported yet.".format(type(filter)))

        image_data = np.full(self.model.ids.shape, -1.0)


        if filter_type == openmc.filter.CellFilter:
            bins = filter.bins

            tally_data = tally.get_values(scores=scores, nuclides=nuclides, value=tally_value)

            for bin_idx, bin in enumerate(bins):
                image_data[self.model.cell_ids == bin] = tally_data[bin_idx][0][0]

        elif filter_type == openmc.filter.MaterialFilter:

            bins = filter.bins

            tally_data = tally.get_values(scores=scores, nuclides=nuclides, value=tally_value)

            for bin_idx, bin in enumerate(bins):
                image_data[self.model.mat_ids == bin] = tally_data[bin_idx][0][0]

        elif filter_type == openmc.filter.MeshFilter:
            cv = self.model.currentView

            mesh = tally.find_filter(openmc.MeshFilter).mesh
            nx, ny, nz = mesh.dimension

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

            # get the slice of the mesh on our coordinate
            k = (cv.origin[ax] - mesh.lower_left[ax]) // mesh.width[ax]

            mesh_data = tally.get_pandas_dataframe(nuclides=False)

            mesh_data = mesh_data[mesh_data['score'] == 'flux']

            mesh_data = mesh_data['mean'].values.reshape(mesh.dimension)

            image_data = mesh_data[:,:,int(k)]

            deltas = (mesh.upper_right - mesh.lower_left) / mesh.dimension
            di = deltas[h_ind]
            dj = deltas[v_ind]
            min_i = int(((cv.origin[h_ind] - cv.width / 2.0) - mesh.lower_left[h_ind]) // di)
            min_i = max(min_i, 0)
            max_i = int(((cv.origin[h_ind] + cv.width / 2.0) - mesh.lower_left[h_ind]) // di)
            max_i = min(max_i, image_data.shape[h_ind])
            min_j = int(((cv.origin[v_ind] - cv.height / 2.0) - mesh.lower_left[v_ind]) // dj)
            min_j = max(min_j, 0)
            max_j = int(((cv.origin[v_ind] + cv.height / 2.0) - mesh.lower_left[v_ind]) // dj)
            max_j = min(max_j, image_data.shape[v_ind])
            print(min_i, max_i, min_j, max_j)

            mask = np.zeros(image_data.shape, dtype=bool)
            mask[min_i:max_i, min_j:max_j] = True
            image_data = image_data[min_i:max_i, min_j:max_j]
            image_data.transpose()

        elif filter_type == openmc.filter.UniverseFilter:
            # get the statepoint summary
            universes = self.model.statepoint.universes

            # set data min/max for the filter as a whole
            tally_data = tally.get_values(scores=scores, nuclides=nuclides, filters=[openmc.UniverseFilter,], filter_bins=[tuple(filter.bins),], value=tally_value)
            data_min = np.min(tally_data)
            data_max = np.max(tally_data)

            # set image data cell for each universe in the filter
            for fbin in filter.bins:
                tally_val = tally.get_values(scores=scores, nuclides=nuclides, filters=[openmc.UniverseFilter,], filter_bins=[(fbin,),])
                tally_val.shape = (1,)
                tally_val = tally_val[0]

                univ_cells = self.model.statepoint.universes[fbin].cells
                for cell in univ_cells:
                    image_data[self.model.cell_ids == cell] = tally_val

        elif filter_type == openmc.filter.MeshFilter:
            pass

        # mask invalid values from the array
        image_data = np.ma.masked_where(image_data < 0.0, image_data)

        data_min = np.min(image_data)
        data_max = np.max(image_data)

        return image_data, data_min, data_max

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


class PlotterDock(QDockWidget):

    def __init__(self, model, FM, parent=None):
        super().__init__(parent)

        self.model = model
        self.FM = FM
        self.mw = parent

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea |
                             QtCore.Qt.RightDockWidgetArea)

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

        for filter in filters:

            filter_label = str(type(filter)).split(".")[-1][:-2]
            filter_item = QTreeWidgetItem(self.filterTree, [filter_label,])

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

class HorizontalLine(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
