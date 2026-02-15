from functools import partial

from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
                               QFormLayout, QComboBox, QSpinBox, QLabel,
                               QDoubleSpinBox, QSizePolicy, QMessageBox,
                               QCheckBox, QRubberBand, QMenu, QDialog,
                               QTabWidget, QTableView, QHeaderView, QListView)
from matplotlib.figure import Figure
from matplotlib import lines as mlines
from matplotlib import font_manager
from matplotlib.colors import SymLogNorm
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from matplotlib.backends.backend_qt5agg import FigureCanvas
import matplotlib.pyplot as plt
import numpy as np
import numpy.ma as ma

from .plot_colors import rgb_normalize, invert_rgb
from .plotmodel import DomainDelegate, PlotModel
from .plotmodel import _NOT_FOUND, _VOID_REGION, _OVERLAP, _MODEL_PROPERTIES
from .scientific_spin_box import ScientificDoubleSpinBox
from .custom_widgets import HorizontalLine

_DEFAULT_FONT_LABEL = "Default (Matplotlib)"
_FONT_FAMILY_CACHE = None


def _matplotlib_font_names():
    global _FONT_FAMILY_CACHE
    if _FONT_FAMILY_CACHE is not None:
        return _FONT_FAMILY_CACHE
    names = set()
    try:
        for entry in font_manager.fontManager.ttflist:
            name = getattr(entry, "name", None)
            if name:
                names.add(name)
    except Exception:
        names = set()
    _FONT_FAMILY_CACHE = sorted(names, key=lambda s: s.lower())
    return _FONT_FAMILY_CACHE


def _build_font_combo():
    combo = QComboBox()
    combo.setEditable(False)
    combo.setMaxVisibleItems(20)
    view = QListView()
    view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    combo.setView(view)
    combo.addItem(_DEFAULT_FONT_LABEL, None)
    for name in _matplotlib_font_names():
        combo.addItem(name, name)
    return combo


class PlotUpdateOverlay(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setStyleSheet("background-color: rgba(20, 20, 20, 140);")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        self.label = QLabel("Generating Plot...", self)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        font = self.label.font()
        font.setPointSize(max(12, font.pointSize() + 6))
        self.label.setFont(font)
        self.label.setStyleSheet("color: white; background-color: transparent;")
        layout.addWidget(self.label)

        self.hide()

    def set_message(self, message: str):
        self.label.setText(message)



class PlotImage(FigureCanvas):

    def __init__(self, model: PlotModel, parent, main_window):

        self.figure = Figure(dpi=main_window.logicalDpiX())
        super().__init__(self.figure)

        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)

        FigureCanvas.updateGeometry(self)
        self.model = model
        self.main_window = main_window
        self.parent = parent

        self.frozen = False

        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.band_origin = QtCore.QPoint()
        self.x_plot_origin = None
        self.y_plot_origin = None

        self.property_colorbar = None
        self.data_indicator = None
        self.tally_data_indicator = None
        self.tally_colorbar = None
        self.tally_image = None
        self.image = None
        self.ax = None

        self._property_colorbar_bg = None
        self._tally_colorbar_bg = None
        self._last_tally_indicator_value = None
        self._last_data_indicator_value = None

        self.menu = QMenu(self)
        self.update_overlay = PlotUpdateOverlay(self)

    def enterEvent(self, event):
        self.setCursor(QtCore.Qt.CrossCursor)
        self.main_window.coord_label.show()

    def leaveEvent(self, event):
        self.main_window.coord_label.hide()
        self.main_window.statusBar().showMessage("")

    def mousePressEvent(self, event):
        self.main_window.coord_label.hide()
        position = event.pos()
        # Set rubber band absolute and relative position
        self.band_origin = position
        self.x_plot_origin, self.y_plot_origin = self.getPlotCoords(position)

        # Create rubber band
        self.rubber_band.setGeometry(QtCore.QRect(self.band_origin,
                                                  QtCore.QSize()))

    def getPlotCoords(self, pos):
        if self.ax is None:
            return (0.0, 0.0)
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
            self.main_window.coord_label.show()
            self.main_window.showCoords(xPlotCoord, yPlotCoord)
        else:
            self.main_window.coord_label.hide()

        return (xPlotCoord, yPlotCoord)

    def _resize(self):
        z = self.main_window.zoom / 100.0
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.update_overlay is not None:
            self.update_overlay.setGeometry(self.rect())

    def showUpdatingOverlay(self, message: str = "Generating Plot..."):
        if self.update_overlay is None:
            return
        self.update_overlay.set_message(message)
        self.update_overlay.setGeometry(self.rect())
        self.update_overlay.raise_()
        self.update_overlay.show()

    def hideUpdatingOverlay(self):
        if self.update_overlay is None:
            return
        self.update_overlay.hide()

    def saveImage(self, filename):
        """Save an image of the current view

        Parameters
        ----------
        filename : str or pathlib.Path
            Name of the image to save
        """
        if "." not in str(filename):
            filename += ".png"
        self.figure.savefig(filename, transparent=True)

    def _colorbar_tick_texts(self, colorbar):
        labels = [t.get_text() for t in colorbar.ax.get_yticklabels()]
        labels = [t for t in labels if t]
        if labels:
            return labels
        try:
            formatter = colorbar.ax.yaxis.get_major_formatter()
            locs = colorbar.get_ticks()
            return [t for t in formatter.format_ticks(locs) if t]
        except Exception:
            return []

    def _text_width_pts(self, text, size, font_name=None):
        if not text:
            return 0.0
        try:
            if font_name:
                prop = FontProperties(size=size, family=font_name)
            else:
                prop = FontProperties(size=size)
            path = TextPath((0, 0), text, prop=prop)
            return path.get_extents().width
        except Exception:
            return 0.6 * size * len(text)

    def _text_height_pts(self, text, size, font_name=None):
        if not text:
            return float(size)
        try:
            if font_name:
                prop = FontProperties(size=size, family=font_name)
            else:
                prop = FontProperties(size=size)
            path = TextPath((0, 0), text, prop=prop)
            return path.get_extents().height
        except Exception:
            return float(size)

    def _colorbar_tick_pad(self, colorbar):
        ticks = colorbar.ax.yaxis.get_major_ticks()
        if ticks:
            try:
                return float(ticks[0].get_pad())
            except Exception:
                pass
        try:
            return float(plt.rcParams.get("ytick.major.pad", 4))
        except Exception:
            return 4.0

    def _colorbar_label_pad(self, colorbar, label_text, label_size, tick_size,
                            label_font=None, tick_font=None):
        # Estimate a label pad that grows with tick label width
        # to avoid label/tick overlap when fonts are enlarged.
        tick_texts = self._colorbar_tick_texts(colorbar)
        max_tick_width = 0.0
        for text in tick_texts:
            max_tick_width = max(max_tick_width,
                                 self._text_width_pts(text, tick_size, tick_font))
        label_height = self._text_height_pts(label_text, label_size, label_font)
        tick_pad = self._colorbar_tick_pad(colorbar)
        return max(15.0, max_tick_width + 0.5 * label_height + tick_pad + 2.0)

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

        if not cv.selectedTally or not cv.tallyDataVisible:
            return -1, None

        # don't look up mesh filter data (for now)
        tally = self.model.statepoint.tallies[cv.selectedTally]

        # check that the position is in the axes view
        v_res, h_res = self.model.tally_data.shape
        if 0 <= yPos < v_res and 0 <= xPos < h_res:
            value = self.model.tally_data[yPos][xPos]
        else:
            value = None

        return cv.selectedTally, value

    def getIDinfo(self, event):

        xPos, yPos = self.getDataIndices(event)

        # check that the position is in the axes view
        if 0 <= yPos < self.model.currentView.v_res \
           and 0 <= xPos and xPos < self.model.currentView.h_res:
            id = self.model.ids[yPos, xPos]
            instance = self.model.instances[yPos, xPos]
            temp = "{:g}".format(self.model.properties[yPos, xPos, 0])
            density = "{:g}".format(self.model.properties[yPos, xPos, 1])
        else:
            id = _NOT_FOUND
            instance = _NOT_FOUND
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

        return id, instance, properties, domain, domain_kind

    def mouseDoubleClickEvent(self, event):
        xCenter, yCenter = self.getPlotCoords(event.pos())
        self.main_window.editPlotOrigin(xCenter, yCenter, apply=True)

    def mouseMoveEvent(self, event):
        cv = self.model.currentView
        if self.ax is None or self.model.image is None:
            return
        # Show Cursor position relative to plot in status bar
        xPlotPos, yPlotPos = self.getPlotCoords(event.pos())

        # Show Cell/Material ID, Name in status bar
        id, instance, properties, domain, domain_kind = self.getIDinfo(event)

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

            if instance != _NOT_FOUND and domain_kind == 'Cell':
                instanceInfo = f" ({instance})"
            else:
                instanceInfo = ""
            if id == _VOID_REGION:
                domainInfo = ("VOID")
            elif id == _OVERLAP:
                domainInfo = ("OVERLAP")
            elif id != _NOT_FOUND and domain[id].name:
                domainInfo = ("{} {}{}: \"{}\"\t Density: {} g/cc\t"
                              "Temperature: {} K".format(
                                  domain_kind,
                                  id,
                                  instanceInfo,
                                  domain[id].name,
                                  density,
                                  temperature
                              ))
            elif id != _NOT_FOUND:
                domainInfo = ("{} {}{}\t Density: {} g/cc\t"
                              "Temperature: {} K".format(domain_kind,
                                                         id,
                                                         instanceInfo,
                                                         density,
                                                         temperature))
            else:
                domainInfo = ""

            if self.model.tally_data is not None:
                tid, value = self.getTallyInfo(event)
                if value is not None and value is not ma.masked:
                    self.updateTallyDataIndicatorValue(value)
                    tallyInfo = "Tally {} {}: {:.5E}".format(
                        tid, cv.tallyValue, float(value))
                else:
                    self.updateTallyDataIndicatorValue(0.0)
        else:
            self.updateTallyDataIndicatorValue(0.0)
            self.updateDataIndicatorValue(0.0)

        if domainInfo:
            self.main_window.statusBar().showMessage(
                " " + domainInfo + "      " + tallyInfo)
        else:
            self.main_window.statusBar().showMessage(" " + tallyInfo)

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
            self.main_window.editPlotOrigin(xCenter, yCenter)

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

            self.main_window.editWidth(width)
            self.main_window.editHeight(height)

    def mouseReleaseEvent(self, event):

        if self.rubber_band.isVisible():
            self.rubber_band.hide()
            self.main_window.applyChanges()
        else:
            plot_manager = self.main_window.plot_manager
            if plot_manager.is_busy or plot_manager.has_pending:
                return
            if self.main_window.model.activeView != self.main_window.model.currentView:
                return
            self.main_window.revertDockControls()

    def wheelEvent(self, event):

        if event.angleDelta() and event.modifiers() == QtCore.Qt.ShiftModifier:
            numDegrees = event.angleDelta() / 8

            if 24 < self.main_window.zoom + numDegrees < 5001:
                self.main_window.editZoom(self.main_window.zoom + numDegrees)

    def contextMenuEvent(self, event):

        self.menu.clear()

        self.main_window.undoAction.setText(
            '&Undo ({})'.format(len(self.model.previousViews)))
        self.main_window.redoAction.setText(
            '&Redo ({})'.format(len(self.model.subsequentViews)))

        id, instance, properties, domain, domain_kind = self.getIDinfo(event)

        cv = self.model.currentView

        # always provide undo option
        self.menu.addSeparator()
        self.menu.addAction(self.main_window.undoAction)
        self.menu.addAction(self.main_window.redoAction)
        self.menu.addSeparator()

        if int(id) not in (_NOT_FOUND, _OVERLAP) and \
           cv.colorby not in _MODEL_PROPERTIES:

            # Domain ID
            if domain[id].name:
                domainID = self.menu.addAction(
                    "{} {} Info: \"{}\"".format(domain_kind, id, domain[id].name))
            else:
                domainID = self.menu.addAction(
                    "{} {} Info".format(domain_kind, id))

            # add connector to a new window of info here for material props
            if domain_kind == 'Material':
                mat_prop_connector = partial(
                    self.main_window.viewMaterialProps, id)
                domainID.triggered.connect(mat_prop_connector)

            self.menu.addSeparator()

            colorAction = self.menu.addAction(
                'Edit {} Color...'.format(domain_kind))
            colorAction.setDisabled(cv.highlighting)
            colorAction.setToolTip('Edit {} color'.format(domain_kind))
            colorAction.setStatusTip('Edit {} color'.format(domain_kind))
            domain_color_connector = partial(self.main_window.editDomainColor,
                                             domain_kind,
                                             id)
            colorAction.triggered.connect(domain_color_connector)

            maskAction = self.menu.addAction('Mask {}'.format(domain_kind))
            maskAction.setCheckable(True)
            maskAction.setChecked(domain[id].masked)
            maskAction.setDisabled(not cv.masking)
            maskAction.setToolTip('Toggle {} mask'.format(domain_kind))
            maskAction.setStatusTip('Toggle {} mask'.format(domain_kind))
            mask_connector = partial(self.main_window.toggleDomainMask,
                                     kind=domain_kind,
                                     id=id)
            maskAction.toggled.connect(mask_connector)

            highlightAction = self.menu.addAction(
                'Highlight {}'.format(domain_kind))
            highlightAction.setCheckable(True)
            highlightAction.setChecked(domain[id].highlight)
            highlightAction.setDisabled(not cv.highlighting)
            highlightAction.setToolTip(
                'Toggle {} highlight'.format(domain_kind))
            highlightAction.setStatusTip(
                'Toggle {} highlight'.format(domain_kind))
            highlight_connector = partial(self.main_window.toggleDomainHighlight,
                                          kind=domain_kind,
                                          id=id)
            highlightAction.toggled.connect(highlight_connector)

        else:
            self.menu.addAction(self.main_window.undoAction)
            self.menu.addAction(self.main_window.redoAction)

            if cv.colorby not in _MODEL_PROPERTIES:
                self.menu.addSeparator()
                if int(id) == _NOT_FOUND:
                    bgColorAction = self.menu.addAction(
                        'Edit Background Color...')
                    bgColorAction.setToolTip('Edit background color')
                    bgColorAction.setStatusTip('Edit plot background color')
                    connector = partial(self.main_window.editBackgroundColor,
                                        apply=True)
                    bgColorAction.triggered.connect(connector)
                elif int(id) == _OVERLAP:
                    olapColorAction = self.menu.addAction(
                        'Edit Overlap Color...')
                    olapColorAction.setToolTip('Edit overlap color')
                    olapColorAction.setStatusTip('Edit plot overlap color')
                    connector = partial(self.main_window.editOverlapColor,
                                        apply=True)
                    olapColorAction.triggered.connect(connector)

        self.menu.addSeparator()
        self.menu.addAction(self.main_window.saveImageAction)
        self.menu.addAction(self.main_window.saveViewAction)
        self.menu.addAction(self.main_window.openAction)
        self.menu.addSeparator()
        self.menu.addMenu(self.main_window.basisMenu)
        self.menu.addMenu(self.main_window.colorbyMenu)
        self.menu.addSeparator()
        if domain_kind.lower() not in ('density', 'temperature'):
            self.menu.addAction(self.main_window.maskingAction)
            self.menu.addAction(self.main_window.highlightingAct)
            self.menu.addAction(self.main_window.overlapAct)
            self.menu.addSeparator()
        self.menu.addAction(self.main_window.dockAction)

        self.main_window.maskingAction.setChecked(cv.masking)
        self.main_window.highlightingAct.setChecked(cv.highlighting)
        self.main_window.overlapAct.setChecked(cv.color_overlaps)

        if self.main_window.dock.isVisible():
            self.main_window.dockAction.setText('Hide &Dock')
        else:
            self.main_window.dockAction.setText('Show &Dock')

        self.menu.exec(event.globalPos())

    def generatePixmap(self, update=False):
        if self.frozen:
            return

        self.main_window.requestPlotUpdate()

    def updatePixmap(self):

        # clear out figure
        self.figure.clear()

        cv = self.model.currentView
        axis_label_size = cv.axisLabelSize
        axis_tick_size = cv.axisTickSize
        colorbar_label_size = cv.colorbarLabelSize
        colorbar_tick_size = cv.colorbarTickSize
        axis_label_font = cv.axisLabelFont
        axis_tick_font = cv.axisTickFont
        colorbar_label_font = cv.colorbarLabelFont
        colorbar_tick_font = cv.colorbarTickFont
        # set figure bg color to match window
        window_bg = self.parent.palette().color(QtGui.QPalette.Window)
        self.figure.patch.set_facecolor(rgb_normalize(window_bg.getRgb()))

        # set data extents for automatic reporting of pointer location
        # in model units
        data_bounds = [cv.origin[self.main_window.xBasis] - cv.width/2.,
                       cv.origin[self.main_window.xBasis] + cv.width/2.,
                       cv.origin[self.main_window.yBasis] - cv.height/2.,
                       cv.origin[self.main_window.yBasis] + cv.height/2.]

        if not hasattr(self.model, 'image') or self.model.image is None:
            return

        ### DRAW DOMAIN IMAGE ###

        # still generate the domain image if the geometric
        # plot isn't visible so mouse-over info can still
        # be shown
        alpha = cv.domainAlpha if cv.domainVisible else 0.0
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

            norm = SymLogNorm(
                1E-10) if cv.color_scale_log[cv.colorby] else None

            data = self.model.properties[:, :, idx]
            self.image = self.figure.subplots().imshow(data,
                                                       cmap=cmap,
                                                       norm=norm,
                                                       extent=data_bounds,
                                                       alpha=cv.domainAlpha)

            # add colorbar
            self.property_colorbar = self.figure.colorbar(self.image,
                                                          anchor=(1.0, 0.0))
            self.property_colorbar.ax.tick_params(labelsize=colorbar_tick_size)
            if colorbar_tick_font:
                for label in self.property_colorbar.ax.get_yticklabels():
                    label.set_fontname(colorbar_tick_font)
            labelpad = self._colorbar_label_pad(self.property_colorbar,
                                                cmap_label,
                                                colorbar_label_size,
                                                colorbar_tick_size,
                                                label_font=colorbar_label_font,
                                                tick_font=colorbar_tick_font)
            if colorbar_label_font:
                label_prop = FontProperties(family=colorbar_label_font)
                self.property_colorbar.set_label(cmap_label,
                                                 rotation=-90,
                                                 labelpad=labelpad,
                                                 fontsize=colorbar_label_size,
                                                 fontproperties=label_prop)
            else:
                self.property_colorbar.set_label(cmap_label,
                                                 rotation=-90,
                                                 labelpad=labelpad,
                                                 fontsize=colorbar_label_size)
            # draw line on colorbar
            dl = self.property_colorbar.ax.dataLim.get_points()
            self.data_indicator = mlines.Line2D(dl[:][0],
                                                [0.0, 0.0],
                                                linewidth=3.,
                                                color='blue',
                                                clip_on=True)
            self.data_indicator.set_animated(True)
            self.property_colorbar.ax.add_line(self.data_indicator)
            self.property_colorbar.ax.margins(0.0, 0.0)
            self.updateDataIndicatorVisibility()
            self.updateColorMinMax(cv.colorby)

        self.ax = self.figure.axes[0]
        self.ax.margins(0.0, 0.0)

        # set axis labels
        axis_label_str = "{} (cm)"
        if axis_label_font:
            axis_label_prop = FontProperties(family=axis_label_font)
            self.ax.set_xlabel(axis_label_str.format(cv.basis[0]),
                               fontsize=axis_label_size,
                               fontproperties=axis_label_prop)
            self.ax.set_ylabel(axis_label_str.format(cv.basis[1]),
                               fontsize=axis_label_size,
                               fontproperties=axis_label_prop)
        else:
            self.ax.set_xlabel(axis_label_str.format(cv.basis[0]),
                               fontsize=axis_label_size)
            self.ax.set_ylabel(axis_label_str.format(cv.basis[1]),
                               fontsize=axis_label_size)
        self.ax.tick_params(axis='both', labelsize=axis_tick_size)
        if axis_tick_font:
            for label in self.ax.get_xticklabels() + self.ax.get_yticklabels():
                label.set_fontname(axis_tick_font)

        # generate tally image
        image_data, extents, data_min, data_max, units = self.model.create_tally_image()

        ### DRAW TALLY IMAGE ###

        # draw tally image
        if image_data is not None:

            if cv.tallyDataMinMaxType != 'custom':
                cv.tallyDataMin = data_min
                cv.tallyDataMax = data_max
            else:
                data_min = cv.tallyDataMin
                data_max = cv.tallyDataMax

            # always mask out negative values
            image_mask = image_data < 0.0

            # mask out invalid values (NaN/Inf)
            image_mask |= ~np.isfinite(image_data)

            if cv.clipTallyData:
                image_mask |= image_data < data_min
                image_mask |= image_data > data_max

            if cv.tallyMaskZeroValues:
                image_mask |= image_data == 0.0

            # mask out invalid values
            image_data = np.ma.masked_where(image_mask, image_data)

            # auto-rescale based on displayed (imshow) data
            if cv.tallyDataMinMaxType == 'visible' and not cv.tallyContours:
                displayed = image_data.compressed()
                if displayed.size:
                    visible_min = float(displayed.min())
                    visible_max = float(displayed.max())
                    # Fall back to full data range if visible range is invalid for log scale
                    if cv.tallyDataLogScale and visible_min <= 0:
                        pass  # keep the full data range
                    else:
                        data_min = visible_min
                        data_max = visible_max
                        cv.tallyDataMin = data_min
                        cv.tallyDataMax = data_max

            if extents is None:
                extents = data_bounds

            self.model.tally_data = image_data
            self.model.tally_extents = extents if extents is not None else data_bounds

            norm = SymLogNorm(1E-30) if cv.tallyDataLogScale else None

            cmap = cv.tallyDataColormap
            if cv.tallyDataReverseCmap:
                cmap += '_r'

            if cv.tallyContours:
                # parse the levels line
                levels = self.parseContoursLine(cv.tallyContourLevels)
                self.tally_image = self.ax.contour(image_data,
                                                   origin='image',
                                                   levels=levels,
                                                   alpha=cv.tallyDataAlpha,
                                                   cmap=cmap,
                                                   norm=norm,
                                                   extent=extents,
                                                   algorithm='serial')

            else:
                self.tally_image = self.ax.imshow(image_data,
                                                  alpha=cv.tallyDataAlpha,
                                                  cmap=cmap,
                                                  norm=norm,
                                                  extent=extents)
            # add colorbar
            self.tally_colorbar = self.figure.colorbar(self.tally_image,
                                                       anchor=(1.0, 0.0))

            if cv.tallyContours:
                fmt = "%.2E"
                self.ax.clabel(self.tally_image,
                               self.tally_image.levels,
                               inline=True,
                               fmt=fmt)

            # draw line on colorbar
            self.tally_data_indicator = mlines.Line2D([0.0, 1.0],
                                                      [0.0, 0.0],
                                                      linewidth=3.,
                                                      color='blue',
                                                      clip_on=True)
            self.tally_data_indicator.set_animated(True)
            self.tally_colorbar.ax.add_line(self.tally_data_indicator)
            self.tally_colorbar.ax.margins(0.0, 0.0)

            self.tally_data_indicator.set_visible(cv.tallyDataIndicator)

            self.main_window.updateTallyMinMax()

            self.tally_colorbar.mappable.set_clim(data_min, data_max)
            self.tally_colorbar.ax.tick_params(labelsize=colorbar_tick_size)
            if colorbar_tick_font:
                for label in self.tally_colorbar.ax.get_yticklabels():
                    label.set_fontname(colorbar_tick_font)
            labelpad = self._colorbar_label_pad(self.tally_colorbar,
                                                units,
                                                colorbar_label_size,
                                                colorbar_tick_size,
                                                label_font=colorbar_label_font,
                                                tick_font=colorbar_tick_font)
            if colorbar_label_font:
                label_prop = FontProperties(family=colorbar_label_font)
                self.tally_colorbar.set_label(units,
                                              rotation=-90,
                                              labelpad=labelpad,
                                              fontsize=colorbar_label_size,
                                              fontproperties=label_prop)
            else:
                self.tally_colorbar.set_label(units,
                                              rotation=-90,
                                              labelpad=labelpad,
                                              fontsize=colorbar_label_size)

        # annotate outlines
        self.add_outlines()
        self.plotSourceSites()

        # annotate mesh boundaries
        for mesh_id in cv.mesh_annotations:
            self.annotate_mesh(mesh_id)

        # always make sure the data bounds are set correctly
        self.ax.set_xbound(data_bounds[0], data_bounds[1])
        self.ax.set_ybound(data_bounds[2], data_bounds[3])
        self.ax.dataLim.x0 = data_bounds[0]
        self.ax.dataLim.x1 = data_bounds[1]
        self.ax.dataLim.y0 = data_bounds[2]
        self.ax.dataLim.y1 = data_bounds[3]

        self.draw()
        self._cache_colorbar_backgrounds()
        self._blit_indicator(self.data_indicator, self.property_colorbar)
        self._blit_indicator(self.tally_data_indicator, self.tally_colorbar)
        return "Done"

    def current_view_data_bounds(self):
        cv = self.model.currentView
        return [cv.origin[self.main_window.xBasis] - cv.width/2.,
                cv.origin[self.main_window.xBasis] + cv.width/2.,
                cv.origin[self.main_window.yBasis] - cv.height/2.,
                cv.origin[self.main_window.yBasis] + cv.height/2.]

    def annotate_mesh(self, mesh_id):
        mesh_bins = self.model.mesh_plot_bins(mesh_id)

        data_bounds = self.current_view_data_bounds()
        self.mesh_contours = self.ax.contour(
            mesh_bins,
            origin='upper',
            colors='k',
            linestyles='solid',
            levels=np.unique(mesh_bins),
            extent=data_bounds,
            algorithm='serial'
        )

    def plotSourceSites(self):
        if not self.model.sourceSitesVisible or self.model.sourceSites is None:
            return

        cv = self.model.currentView
        basis = cv.view_params.basis

        h_idx = 'xyz'.index(basis[0])
        v_idx = 'xyz'.index(basis[1])

        sites = self.model.sourceSites

        slice_ax = cv.view_params.slice_axis

        if self.model.sourceSitesApplyTolerance:
            sites_to_plot = sites[np.abs(sites[:, slice_ax] - cv.origin[slice_ax]) <= self.model.sourceSitesTolerance]
        else:
            sites_to_plot = sites

        self.ax.scatter([s[h_idx] for s in sites_to_plot],
                        [s[v_idx] for s in sites_to_plot],
                        marker='o',
                        color=rgb_normalize(self.model.sourceSitesColor))

    def add_outlines(self):
        cv = self.model.currentView
        # draw outlines as isocontours
        if cv.outlinesCell or cv.outlinesMat:
            # set data extents for automatic reporting of pointer location
            data_bounds = self.current_view_data_bounds()
            if cv.outlinesCell:
                levels = np.unique(self.model.cell_ids)
                self.ax.contour(self.model.cell_ids,
                                origin='upper',
                                colors='k',
                                linestyles='solid',
                                levels=levels,
                                extent=data_bounds,
                                algorithm='serial')
            if cv.outlinesMat:
                levels = np.unique(self.model.mat_ids)
                self.ax.contour(self.model.mat_ids,
                                origin='upper',
                                colors='k',
                                linestyles='solid',
                                levels=levels,
                                extent=data_bounds,
                                algorithm='serial')


    @staticmethod
    def parseContoursLine(line):
        # if there are any commas in the line, treat as level values
        line = line.strip()
        if ',' in line:
            return [float(val) for val in line.split(",") if val != '']
        else:
            return int(line)

    def updateColorbarScale(self):
        self.updatePixmap()

    def _cache_colorbar_backgrounds(self):
        """Cache colorbar backgrounds for fast indicator blitting."""
        self._property_colorbar_bg = None
        self._tally_colorbar_bg = None

        if self.property_colorbar and self.data_indicator:
            self._property_colorbar_bg = self.copy_from_bbox(
                self.property_colorbar.ax.bbox)

        if self.tally_colorbar and self.tally_data_indicator:
            self._tally_colorbar_bg = self.copy_from_bbox(
                self.tally_colorbar.ax.bbox)

    def _blit_indicator(self, indicator, colorbar):
        """Blit a single indicator line onto its colorbar if possible."""
        if colorbar is None or indicator is None:
            return False

        if not indicator.get_visible():
            return False

        if colorbar is self.property_colorbar:
            background = self._property_colorbar_bg
        else:
            background = self._tally_colorbar_bg

        if background is None:
            return False

        self.restore_region(background)
        colorbar.ax.draw_artist(indicator)
        self.blit(colorbar.ax.bbox)
        return True

    def updateTallyDataIndicatorValue(self, y_val):
        cv = self.model.currentView

        if not cv.tallyDataVisible or not cv.tallyDataIndicator:
            return

        if self.tally_data_indicator is not None and self.tally_image is not None:
            # use norm to get axis value if log scale
            if cv.tallyDataLogScale:
                y_val = self.tally_image.norm(y_val)

            # If indicator value hasn't changed, skip update
            if self._last_tally_indicator_value == y_val:
                return
            self._last_tally_indicator_value = y_val

            data = self.tally_data_indicator.get_data()
            self.tally_data_indicator.set_data([data[0], [y_val, y_val]])
            dl_color = invert_rgb(self.tally_image.get_cmap()(y_val), True)
            self.tally_data_indicator.set_c(dl_color)

            if not self._blit_indicator(self.tally_data_indicator, self.tally_colorbar):
                self.draw_idle()

    def updateDataIndicatorValue(self, y_val):
        cv = self.model.currentView

        if cv.colorby not in _MODEL_PROPERTIES or \
           not cv.data_indicator_enabled[cv.colorby]:
            return

        if self.data_indicator and self.image is not None:
            # use norm to get axis value if log scale
            if cv.color_scale_log[cv.colorby]:
                y_val = self.image.norm(y_val)

            # If indicator value hasn't changed, skip update
            if self._last_data_indicator_value == y_val:
                return
            self._last_data_indicator_value = y_val

            data = self.data_indicator.get_data()
            self.data_indicator.set_data([data[0], [y_val, y_val]])
            dl_color = invert_rgb(self.image.get_cmap()(y_val), True)
            self.data_indicator.set_c(dl_color)

            if not self._blit_indicator(self.data_indicator, self.property_colorbar):
                self.draw_idle()

    def updateDataIndicatorVisibility(self):
        cv = self.model.currentView
        if self.data_indicator and cv.colorby in _MODEL_PROPERTIES:
            val = cv.data_indicator_enabled[cv.colorby]
            self.data_indicator.set_visible(val)
            if not self._blit_indicator(self.data_indicator, self.property_colorbar):
                self.draw_idle()

    def updateColorMap(self, colormap_name, property_type):
        if self.property_colorbar and property_type == self.model.activeView.colorby:
            self.image.set_cmap(colormap_name)
            self.figure.draw_without_rendering()
            self.draw()
            self._cache_colorbar_backgrounds()
            self._blit_indicator(self.data_indicator, self.property_colorbar)

    def updateColorMinMax(self, property_type):
        av = self.model.activeView
        if self.property_colorbar and property_type == av.colorby:
            clim = av.getColorLimits(property_type)
            self.property_colorbar.mappable.set_clim(*clim)
            self.data_indicator.set_data(clim[:2],
                                         (0.0, 0.0))
            self.figure.draw_without_rendering()
            self.draw()
            self._cache_colorbar_backgrounds()
            self._blit_indicator(self.data_indicator, self.property_colorbar)


class ColorDialog(QDialog):

    def __init__(self, model, font_metric, parent=None):
        super().__init__(parent)

        self.setWindowTitle('Color Options')

        self.model = model
        self.font_metric = font_metric
        self.main_window = parent

        self.createDialogLayout()

    def createDialogLayout(self):

        self.createGeneralTab()

        self.cellTable = self.createDomainTable(self.main_window.cellsModel)
        self.matTable = self.createDomainTable(self.main_window.materialsModel)
        self.tabs = {'cell': self.createDomainTab(self.cellTable),
                     'material': self.createDomainTab(self.matTable),
                     'temperature': self.createPropertyTab('temperature'),
                     'density': self.createPropertyTab('density')}

        self.tab_bar = QTabWidget()
        self.tab_bar.setMaximumHeight(800)
        self.tab_bar.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
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

        main_window = self.main_window

        # Masking options
        self.maskingCheck = QCheckBox('')
        self.maskingCheck.stateChanged.connect(main_window.toggleMasking)

        button_width = self.font_metric.boundingRect("XXXXXXXXXX").width()
        self.maskColorButton = QPushButton()
        self.maskColorButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.maskColorButton.setFixedWidth(button_width)
        self.maskColorButton.setFixedHeight(self.font_metric.height() * 1.5)
        self.maskColorButton.clicked.connect(main_window.editMaskingColor)

        # Highlighting options
        self.hlCheck = QCheckBox('')
        self.hlCheck.stateChanged.connect(main_window.toggleHighlighting)

        self.hlColorButton = QPushButton()
        self.hlColorButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.hlColorButton.setFixedWidth(button_width)
        self.hlColorButton.setFixedHeight(self.font_metric.height() * 1.5)
        self.hlColorButton.clicked.connect(main_window.editHighlightColor)

        self.alphaBox = QDoubleSpinBox()
        self.alphaBox.setRange(0, 1)
        self.alphaBox.setSingleStep(.05)
        self.alphaBox.valueChanged.connect(main_window.editAlpha)

        self.seedBox = QSpinBox()
        self.seedBox.setRange(1, 999)
        self.seedBox.valueChanged.connect(main_window.editSeed)

        # General options
        self.bgButton = QPushButton()
        self.bgButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.bgButton.setFixedWidth(button_width)
        self.bgButton.setFixedHeight(self.font_metric.height() * 1.5)
        self.bgButton.clicked.connect(main_window.editBackgroundColor)

        self.colorbyBox = QComboBox(self)
        self.colorbyBox.addItem("material")
        self.colorbyBox.addItem("cell")
        self.colorbyBox.addItem("temperature")
        self.colorbyBox.addItem("density")
        self.colorbyBox.currentTextChanged[str].connect(
            main_window.editColorBy)

        self.universeLevelBox = QComboBox(self)
        self.universeLevelBox.addItem('all')
        for i in range(self.model.max_universe_levels):
            self.universeLevelBox.addItem(str(i))
        self.universeLevelBox.currentTextChanged[str].connect(
            main_window.editUniverseLevel)

        # Overlap plotting
        self.overlapCheck = QCheckBox('', self)
        overlap_connector = partial(main_window.toggleOverlaps)
        self.overlapCheck.stateChanged.connect(overlap_connector)

        self.overlapColorButton = QPushButton()
        self.overlapColorButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.overlapColorButton.setFixedWidth(button_width)
        self.overlapColorButton.setFixedHeight(self.font_metric.height() * 1.5)
        self.overlapColorButton.clicked.connect(main_window.editOverlapColor)

        self.colorResetButton = QPushButton("&Reset Colors")
        self.colorResetButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.colorResetButton.clicked.connect(main_window.resetColors)

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
        formLayout.addRow('Overlap Color:', self.overlapColorButton)
        formLayout.addRow(HorizontalLine())
        formLayout.addRow('Color Plot By:', self.colorbyBox)
        formLayout.addRow('Universe Level:', self.universeLevelBox)
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
        connector1 = partial(self.main_window.toggleUserMinMax,
                             property=property_kind)
        propertyTab.minMaxCheckBox.stateChanged.connect(connector1)

        propertyTab.minBox = ScientificDoubleSpinBox(self)
        propertyTab.minBox.setMaximum(1E9)
        propertyTab.minBox.setMinimum(0)
        propertyTab.maxBox = ScientificDoubleSpinBox(self)
        propertyTab.maxBox.setMaximum(1E9)
        propertyTab.maxBox.setMinimum(0)

        connector2 = partial(self.main_window.editColorbarMin,
                             property_type=property_kind)
        propertyTab.minBox.valueChanged.connect(connector2)
        connector3 = partial(self.main_window.editColorbarMax,
                             property_type=property_kind)
        propertyTab.maxBox.valueChanged.connect(connector3)

        propertyTab.colormapBox = QComboBox(self)
        cmaps = sorted(m for m in plt.colormaps()
                       if not m.endswith("_r"))
        for cmap in cmaps:
            propertyTab.colormapBox.addItem(cmap)

        connector = partial(self.main_window.editColorMap,
                            property_type=property_kind)

        propertyTab.colormapBox.currentTextChanged[str].connect(connector)

        propertyTab.dataIndicatorCheckBox = QCheckBox()
        propertyTab.dataIndicatorCheckBox.setCheckable(True)
        connector4 = partial(self.main_window.toggleDataIndicatorCheckBox,
                             property=property_kind)
        propertyTab.dataIndicatorCheckBox.stateChanged.connect(connector4)

        propertyTab.colorBarScaleCheckBox = QCheckBox()
        propertyTab.colorBarScaleCheckBox.setCheckable(True)
        connector5 = partial(self.main_window.toggleColorbarScale,
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
            idx = self.tabs[key].colormapBox.findText(
                val,
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
            self.tabs[key].minBox.setEnabled(val)
            self.tabs[key].maxBox.setEnabled(val)

    def updateColorbarScale(self):
        av = self.model.activeView
        for key, val in av.color_scale_log.items():
            self.tabs[key].colorBarScaleCheckBox.setChecked(val)

    def createButtonBox(self):

        applyButton = QPushButton("Apply Changes")
        applyButton.clicked.connect(self.main_window.applyChanges)
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
        self.updateUniverseLevel()
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
        color = self.model.activeView.domainBackground
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
        self.universeLevelBox.setEnabled(colorby == 'cell')

    def updateUniverseLevel(self):
        level = self.model.activeView.level
        if level == -1:
            self.universeLevelBox.setCurrentText('all')
        else:
            self.universeLevelBox.setCurrentText(str(level))

    def updateDomainTabs(self):
        self.cellTable.setModel(self.main_window.cellsModel)
        self.matTable.setModel(self.main_window.materialsModel)


class AppearanceDialog(QDialog):

    def __init__(self, model, font_metric, parent=None):
        super().__init__(parent)

        self.setWindowTitle('Appearance')

        self.model = model
        self.font_metric = font_metric
        self.main_window = parent

        self.createDialogLayout()

    def createDialogLayout(self):
        self.axisLabelSizeBox = QSpinBox()
        self.axisLabelSizeBox.setRange(1, 96)
        self.axisLabelSizeBox.setSuffix(" pt")
        self.axisLabelSizeBox.valueChanged.connect(
            self.main_window.editAxisLabelFontSize)

        self.axisTickSizeBox = QSpinBox()
        self.axisTickSizeBox.setRange(1, 96)
        self.axisTickSizeBox.setSuffix(" pt")
        self.axisTickSizeBox.valueChanged.connect(
            self.main_window.editAxisTickFontSize)

        self.colorbarLabelSizeBox = QSpinBox()
        self.colorbarLabelSizeBox.setRange(1, 96)
        self.colorbarLabelSizeBox.setSuffix(" pt")
        self.colorbarLabelSizeBox.valueChanged.connect(
            self.main_window.editColorbarLabelFontSize)

        self.colorbarTickSizeBox = QSpinBox()
        self.colorbarTickSizeBox.setRange(1, 96)
        self.colorbarTickSizeBox.setSuffix(" pt")
        self.colorbarTickSizeBox.valueChanged.connect(
            self.main_window.editColorbarTickFontSize)

        self.axisLabelFontBox = _build_font_combo()
        self.axisLabelFontBox.currentIndexChanged.connect(
            lambda _: self.main_window.editAxisLabelFont(
                self.axisLabelFontBox.currentData()))

        self.axisTickFontBox = _build_font_combo()
        self.axisTickFontBox.currentIndexChanged.connect(
            lambda _: self.main_window.editAxisTickFont(
                self.axisTickFontBox.currentData()))

        self.colorbarLabelFontBox = _build_font_combo()
        self.colorbarLabelFontBox.currentIndexChanged.connect(
            lambda _: self.main_window.editColorbarLabelFont(
                self.colorbarLabelFontBox.currentData()))

        self.colorbarTickFontBox = _build_font_combo()
        self.colorbarTickFontBox.currentIndexChanged.connect(
            lambda _: self.main_window.editColorbarTickFont(
                self.colorbarTickFontBox.currentData()))

        formLayout = QFormLayout()
        formLayout.setAlignment(QtCore.Qt.AlignHCenter)
        formLayout.setFormAlignment(QtCore.Qt.AlignHCenter)
        formLayout.setLabelAlignment(QtCore.Qt.AlignLeft)
        formLayout.addRow('Axis Labels:', self.axisLabelSizeBox)
        formLayout.addRow('Axis Label Font:', self.axisLabelFontBox)
        formLayout.addRow('Axis Ticks:', self.axisTickSizeBox)
        formLayout.addRow('Axis Tick Font:', self.axisTickFontBox)
        formLayout.addRow(HorizontalLine())
        formLayout.addRow('Colorbar Labels:', self.colorbarLabelSizeBox)
        formLayout.addRow('Colorbar Label Font:', self.colorbarLabelFontBox)
        formLayout.addRow('Colorbar Ticks:', self.colorbarTickSizeBox)
        formLayout.addRow('Colorbar Tick Font:', self.colorbarTickFontBox)

        self.createButtonBox()

        layout = QVBoxLayout()
        layout.addLayout(formLayout)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)

    def createButtonBox(self):
        applyButton = QPushButton("Apply Changes")
        applyButton.clicked.connect(self.main_window.applyChanges)
        applyButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(applyButton, 1)

        self.buttonBox = QWidget()
        self.buttonBox.setLayout(buttonLayout)

    def updateDialogValues(self):
        av = self.model.activeView
        boxes = (
            self.axisLabelSizeBox,
            self.axisTickSizeBox,
            self.colorbarLabelSizeBox,
            self.colorbarTickSizeBox,
            self.axisLabelFontBox,
            self.axisTickFontBox,
            self.colorbarLabelFontBox,
            self.colorbarTickFontBox,
        )
        for box in boxes:
            box.blockSignals(True)

        self.axisLabelSizeBox.setValue(av.axisLabelSize)
        self.axisTickSizeBox.setValue(av.axisTickSize)
        self.colorbarLabelSizeBox.setValue(av.colorbarLabelSize)
        self.colorbarTickSizeBox.setValue(av.colorbarTickSize)
        av.axisLabelFont = self._set_font_box(self.axisLabelFontBox, av.axisLabelFont)
        av.axisTickFont = self._set_font_box(self.axisTickFontBox, av.axisTickFont)
        av.colorbarLabelFont = self._set_font_box(self.colorbarLabelFontBox, av.colorbarLabelFont)
        av.colorbarTickFont = self._set_font_box(self.colorbarTickFontBox, av.colorbarTickFont)

        for box in boxes:
            box.blockSignals(False)

    def _set_font_box(self, box, value):
        idx = box.findData(value)
        if idx < 0:
            idx = box.findData(None)
        if idx < 0:
            idx = 0
        box.setCurrentIndex(idx)
        return box.currentData()
