import copy, struct, threading, openmc
import numpy as np
import xml.etree.ElementTree as ET
from ast import literal_eval
from PySide2.QtWidgets import QTableView, QItemDelegate, QColorDialog, QLineEdit
from PySide2.QtCore import QAbstractTableModel, QModelIndex, Qt, QSize, QEvent
from PySide2.QtGui import QColor

ID, NAME, COLOR, COLORLABEL, MASK, HIGHLIGHT = (range(0,6))

class PlotModel():
    """ Geometry and plot settings for OpenMC Plot Explorer model

        Attributes
        ----------
        geom : openmc.Geometry instance
            OpenMC Geometry of the model
        modelCells : collections.OrderedDict
            Dictionary mapping cell IDs to openmc.Cell instances
        modelMaterials : collections.OrderedDict
            Dictionary mapping material IDs to openmc.Material instances
        ids : Dictionary
            Dictionary mapping plot coordinates to cell/material ID
        previousViews : list of PlotView instances
            List of previously created plot view settings used to undo
            changes made in plot explorer
        subsequentViews : list of PlotView instances
            List of undone plot view settings used to redo changes made
            in plot explorer
        defaultView : PlotView instance
            Default settings for given geometry
        currentView : PlotView instance
            Currently displayed plot settings in plot explorer
        activeView : PlotView instance
            Active state of settings in plot explorer, which may or may not
            have unapplied changes
    """

    def __init__(self):
        """ Initialize PlotModel class attributes """

        # Read geometry.xml
        self.geom = openmc.Geometry.from_xml('geometry.xml')

        # Retrieve OpenMC Cells/Materials
        self.modelCells = self.geom.get_all_cells()
        self.modelMaterials = self.geom.get_all_materials()

        # Cell/Material ID by coordinates
        self.ids = None

        self.previousViews = []
        self.subsequentViews = []
        self.defaultView = self.getDefaultView()
        self.currentView = copy.deepcopy(self.defaultView)
        self.activeView = copy.deepcopy(self.defaultView)

    def getDefaultView(self):
        """ Generates default PlotView instance for OpenMC geometry

        Centers plot view origin in every dimension if possible. Defaults
        to xy basis, with height and width to accomodate full size of
        geometry. Defaults to (0, 0, 0) origin with width and heigth of
        25 if geometry bounding box cannot be generated.

        Returns
        -------
        default : PlotView instance
            PlotView instance with default view settings
        """

        lower_left, upper_right = self.geom.bounding_box

        # Check for valid bounding_box dimensions
        if -np.inf not in lower_left[:2] and np.inf not in upper_right[:2]:
            xcenter = (upper_right[0] + lower_left[0])/2
            width = abs(upper_right[0] - lower_left[0]) * 1.005
            ycenter = (upper_right[1] + lower_left[1])/2
            height = abs(upper_right[1] - lower_left[1]) * 1.005
        else:
            xcenter, ycenter, width, height = (0.00, 0.00, 25, 25)

        if lower_left[2] != -np.inf and upper_right[2] != np.inf:
            zcenter = (upper_right[2] + lower_left[2])/2
        else:
            zcenter = 0.00

        default = PlotView([xcenter, ycenter, zcenter], width, height)
        return default

    def updateIDs(self):
        """ Update ids attribute to reflect current plot view """

        with open('plot_ids.binary', 'rb') as f:
            px, py, wx, wy = struct.unpack('iidd', f.read(4*2 + 8*2))
            ids = np.zeros((py, px), dtype=int)
            for i in range(py):
                ids[i] = struct.unpack('{}i'.format(px), f.read(4*px))
        self.ids = ids

    def generatePlot(self):
        """ Spawn thread from which to generate new plot image """

        t = threading.Thread(target=self.makePlot)
        t.start()
        t.join()

    def makePlot(self):
        """ Generate new plot image from active view settings

        Creates corresponding .xml files from user-chosen settings.
        Runs OpenMC in plot mode to generate new plot image.
        """

        cv = self.currentView = copy.deepcopy(self.activeView)

        plot = openmc.Plot()
        plot.filename = 'plot'
        plot.color_by = cv.colorby
        plot.basis = cv.basis
        plot.origin = cv.origin
        plot.width = (cv.width, cv.height)
        plot.pixels = (cv.hRes, cv.vRes)
        plot.background = cv.plotBackground

        # Determine domain type and source
        if cv.colorby == 'cell':
            domain = self.currentView.cells
            source = self.modelCells
        else:
            domain = self.currentView.materials
            source = self.modelMaterials

        # Custom Colors
        plot.colors = {}
        for id, dom in domain.items():
            if dom.color:
                plot.colors[source[int(id)]] = dom.color

        # Masking options
        if cv.masking:
            plot.mask_components = []
            for id, dom in domain.items():
                if not dom.masked:
                    plot.mask_components.append(source[int(id)])
            plot.mask_background = cv.maskBackground

        # Highlighting options
        if cv.highlighting:
            domains = []
            for id, dom in domain.items():
                if dom.highlighted:
                    domains.append(source[int(id)])
            background = cv.highlightBackground
            alpha = cv.highlightAlpha
            seed = cv.highlightSeed

            plot.highlight_domains(self.geom, domains, seed, alpha, background)

        # Generate plot.xml
        plots = openmc.Plots([plot])
        plots.export_to_xml()
        openmc.plot_geometry()

        self.updateIDs()

    def undo(self):
        """ Revert to previous PlotView instance. Re-generate plot image """

        if self.previousViews:
            self.subsequentViews.append(copy.deepcopy(self.currentView))
            self.activeView = self.previousViews.pop()
            self.generatePlot()

    def redo(self):
        """ Revert to subsequent PlotView instance. Re-generate plot image """

        if self.subsequentViews:
            self.storeCurrent()
            self.activeView = self.subsequentViews.pop()
            self.generatePlot()

    def storeCurrent(self):
        """ Add current view to previousViews list """
        self.previousViews.append(copy.deepcopy(self.currentView))


class PlotView():
    """ View settings for OpenMC plot.

    Parameters
    ----------
    origin : 3-tuple of floats
        Origin (center) of plot view
    width: float
        Width of plot view in model units
    height : float
        Height of plot view in model units

    Attributes
    ----------
    origin : 3-tuple of floats
        Origin (center) of plot view
    width : float
        Width of the plot view in model units
    height : float
        Height of the plot view in model units
    hRes : int
        Horizontal resolution of plot image
    vRes : int
        Vertical resolution of plot image
    aspectLock : bool
        Indication of whether aspect lock should be maintained to
        prevent image stretching/warping
    basis : {'xy', 'xz', 'yz'}
        The basis directions for the plot
    colorby : {'cell', 'material'}
        Indication of whether the plot should be colored by cell or material
    masking : bool
        Indication of whether cell/material masking is active
    maskBackground : 3-tuple of int
        RGB color to apply to masked cells/materials
    highlighting: bool
        Indication of whether cell/material highlighting is active
    highlightBackground : 3-tuple of int
        RGB color to apply to non-highlighted cells/materials
    highlightAlpha : float between 0 and 1
        Alpha value for highlight background color
    highlightSeed : int
        Random number seed used to generate color scheme when highlighting
        is active
    plotBackground : 3-tuple of int
        RGB color to apply to plot background
    cells : Dict of DomainView instances
        Dictionary of cell view settings by ID
    materials : Dict of DomainView instances
        Dictionary of material view settings by ID
    """

    def __init__(self, origin, width, height):
        """ Initialize PlotView attributes """

        self.origin = origin
        self.width = width
        self.height = height

        self.hRes = 600
        self.vRes = 600
        self.aspectLock = True

        self.basis = 'xy'
        self.colorby = 'material'

        self.masking = True
        self.maskBackground = (0,0,0)
        self.highlighting = False
        self.highlightBackground = (80, 80, 80)
        self.highlightAlpha = 0.5
        self.highlightSeed = 1
        self.plotBackground = (50, 50, 50)

        self.cells = self.getDomains('geometry.xml', 'cell')
        self.materials = self.getDomains('materials.xml', 'material')

    def __eq__(self, other):
        if isinstance(other, PlotView):
            return self.__dict__ == other.__dict__

    def __ne__(self, other):
        if isinstance(other, PlotView):
            return self.__dict__ != other.__dict__

    def getDomains(self, file, type_):
        """ Return dictionary of domain settings.

        Retrieve cell or material ID numbers and names from .xml files
        and convert to DomainView instances with default view settings.

        Parameters
        ----------
        file : {'geometry.xml', 'materials.xml'}
            .xml file from which to retrieve values
        type_ : {'cell', 'material'}
            Type of domain to retrieve for dictionary

        Returns
        -------
        domains : Dictionary of DomainView instances
            Dictionary of cell/material DomainView instances keyed by ID
        """

        doc = ET.parse(file)
        root = doc.getroot()

        domains = {}
        for dom in root.findall(type_):
            id = dom.attrib['id']
            if 'name' in dom.attrib:
                name = dom.attrib['name']
            else:
                name = None
            color = None
            masked = False
            highlighted = False
            domain = DomainView(id, name, color, masked, highlighted)
            domains[id] = domain

        return domains


class DomainView():
    """ Represents view settings for OpenMC cell or material.

    Parameters
    ----------
    id : int
        Unique identifier for cell/material
    name : str
        Name of cell/material
    color : 3-tuple of int or str
        RGB or SVG color of cell/material (defaults to None)
    masked : bool
        Indication of whether cell/material should be masked
        (defaults to False)
    highlighted : bool
        Indication of whether cell/material should be highlighted
        (defaults to False)
    """

    def __init__(self, id, name, color=None, masked=False, highlighted=False):
        """ Initialize DomainView instance """

        self.id = id
        self.name = name
        self.color = color
        self.masked = masked
        self.highlighted = highlighted

    def __repr__(self):
        return (f"id: {self.id} \nname: {self.name} \ncolor: {self.color} \
                \nmask: {self.masked} \nhighlight: {self.highlighted}\n\n")

    def __eq__(self, other):
        if isinstance(other, DomainView):
            return self.__dict__ == other.__dict__


class DomainTableModel(QAbstractTableModel):
    """ Abstract Table Model of cell/material view attributes """

    def __init__(self, domains):
        super(DomainTableModel, self).__init__()
        self.domains = [dom for dom in domains.values()]

    def rowCount(self, index=QModelIndex()):
        return len(self.domains)

    def columnCount(self, index=QModelIndex()):
        return 6

    def data(self, index, role=Qt.DisplayRole):

        if not index.isValid() or not (0 <= index.row() < len(self.domains)):
            return None

        domain = self.domains[index.row()]
        column = index.column()

        if role == Qt.DisplayRole:
            if column == ID:
                return domain.id
            elif column == NAME:
                return domain.name if domain.name is not None else '--'
            elif column == COLOR:
                return '' if domain.color is not None else '+'
            elif column == COLORLABEL:
                return str(domain.color) if domain.color is not None else '--'
            elif column == MASK:
                return None
            elif column == HIGHLIGHT:
                return None

        elif role == Qt.ToolTipRole:
            if column == NAME:
                return 'Double-click to edit'
            elif column in (COLOR, COLORLABEL):
                return 'Double-click to edit \nRight-click to clear'
            elif column in (MASK, HIGHLIGHT):
                return 'Click to toggle'

        elif role == Qt.TextAlignmentRole:
            if column in (MASK, HIGHLIGHT, COLOR):
                return int(Qt.AlignCenter | Qt.AlignVCenter)
            else:
                return int(Qt.AlignLeft | Qt.AlignVCenter)

        elif role == Qt.BackgroundColorRole:
            if column == COLOR:
                if isinstance(domain.color, tuple):
                        return QColor.fromRgb(*domain.color)
                elif isinstance(domain.color, str):
                    return QColor.fromRgb(*openmc.plots._SVG_COLORS[domain.color])

        elif role == Qt.CheckStateRole:
            if column == MASK:
                return Qt.Checked if domain.masked else Qt.Unchecked
            elif column == HIGHLIGHT:
                return Qt.Checked if domain.highlighted else Qt.Unchecked

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):

        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return int(Qt.AlignLeft|Qt.AlignVCenter)
            return int(Qt.AlignRight|Qt.AlignVCenter)

        elif role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                headers = ['ID', 'Name', 'Color', 'SVG/RGB', 'Mask', 'Highlight']
                return headers[section]
            return int(section + 1)

        return None

    def flags(self, index):

        if not index.isValid():
            return Qt.ItemIsEnabled

        elif index.column() in (MASK, HIGHLIGHT):
            return Qt.ItemFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable |
                                Qt.ItemIsSelectable)
        elif index.column() in (NAME, COLORLABEL):
            return Qt.ItemFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable |
                                Qt.ItemIsSelectable)
        elif index.column() == COLOR:
            return Qt.ItemFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable)
        else:
            return Qt.ItemFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

    def setData(self, index, value, role=Qt.EditRole):

        if not index.isValid() or not (0 <= index.row() < len(self.domains)):
            return False

        domain = self.domains[index.row()]
        column = index.column()

        if column == NAME:
            domain.name = value if value else None
        elif column == COLOR:
            domain.color = value
        elif column == COLORLABEL:
            domain.color = value
        elif column == MASK:
            if role == Qt.CheckStateRole:
                domain.masked = True if value == Qt.Checked else False
        elif column == HIGHLIGHT:
            if role == Qt.CheckStateRole:
                domain.highlighted = True if value == Qt.Checked else False

        self.dataChanged.emit(index, index)
        return True


class DomainDelegate(QItemDelegate):
    def __init__(self, parent=None):
        super(DomainDelegate, self).__init__(parent)

    def sizeHint(self, option, index):

        fm = option.fontMetrics
        column = index.column()

        if column == ID:
            return QSize(fm.width("XXXXXX"), fm.height())
        elif column == COLOR:
            return QSize(fm.width("XXXXXX"), fm.height())
        elif column == COLORLABEL:
            return QSize(fm.width("X(XXX, XXX, XXX)X"), fm.height())
        elif column == MASK:
            return QSize(fm.width("XXXX"), fm.height())
        else:
            return QItemDelegate.sizeHint(self, option, index)

    def createEditor(self, parent, option, index):

        if index.column() == COLOR:
            dialog = QColorDialog(parent)
            return dialog
        elif index.column() == COLORLABEL:
            return QLineEdit(parent)
        else:
            return QItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, editor, index):

        if index.column() == COLOR:
            color = index.data(Qt.BackgroundColorRole)
            color = 'white' if color is None else color
            editor.setCurrentColor(color)
        elif index.column() in (NAME, COLORLABEL):
            text = index.data(Qt.DisplayRole)
            if text != '--':
                editor.setText(text)

    def editorEvent(self, event, model, option, index):

        if index.column() in (COLOR, COLORLABEL):
            if not int(index.flags() & Qt.ItemIsEditable) > 0:
                return False
            if event.type() == QEvent.MouseButtonRelease \
                and event.button() == Qt.RightButton:
                self.setModelData(None, model, index)
                return True
            return False
        else:
            return QItemDelegate.editorEvent(self, event, model, option, index)

    def setModelData(self, editor, model, index):

        row = index.row()
        column = index.column()

        if column == COLOR and editor is None:
            model.setData(index, None, Qt.BackgroundColorRole)
            model.setData(model.index(row, column+1), None, Qt.DisplayRole)
        elif column == COLOR:
            color = editor.currentColor()
            if color != QColor():
                color = color.getRgb()[:3]
                model.setData(index, color, Qt.BackgroundColorRole)
                model.setData(model.index(row, column+1), color, Qt.DisplayRole)
        elif column == COLORLABEL:
            if editor is None:
                model.setData(model.index(row, column-1), None, Qt.BackgroundColorRole)
                model.setData(index, None, Qt.DisplayRole)
            elif editor.text().lower() in openmc.plots._SVG_COLORS:
                svg = editor.text().lower()
                color = openmc.plots._SVG_COLORS[svg]
                model.setData(model.index(row, column-1), color, Qt.BackgroundColorRole)
                model.setData(index, svg, Qt.DisplayRole)
            else:
                try:
                    input = literal_eval(editor.text())
                except (ValueError, SyntaxError):
                    return None
                if not isinstance(input, tuple) or len(input) != 3:
                    return None
                for val in input:
                    if not isinstance(val, int) or not 0 <= val <= 255:
                        return None
                model.setData(model.index(row, column-1), input, Qt.BackgroundColorRole)
                model.setData(index, input, Qt.DisplayRole)
        else:
            QItemDelegate.setModelData(self, editor, model, index)
