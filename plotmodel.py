import copy, struct, openmc
import numpy as np
import xml.etree.ElementTree as ET
from threading import Thread
from PySide2.QtWidgets import QTableView, QItemDelegate, QColorDialog
from PySide2.QtCore import QAbstractTableModel, QModelIndex, Qt, QSize, QEvent
from PySide2.QtGui import QColor


ID, NAME, COLOR, COLORLABEL, MASK, HIGHLIGHT = (range(0,6))

class PlotModel():
    def __init__(self):

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

        # Get bounding box
        lower_left, upper_right = self.geom.bounding_box

        # Check for valid dimension
        if -np.inf not in lower_left[:2] and np.inf not in upper_right[:2]:
            xcenter = (upper_right[0] + lower_left[0])/2
            width = abs(upper_right[0] - lower_left[0])
            ycenter = (upper_right[1] + lower_left[1])/2
            height = abs(upper_right[1] - lower_left[1])
        else:
            xcenter, ycenter, width, height = (0.00, 0.00, 25, 25)

        if lower_left[2] != -np.inf and upper_right[2] != np.inf:
            zcenter = (upper_right[2] + lower_left[2])/2
        else:
            zcenter = 0.00

        default = PlotView([xcenter, ycenter, zcenter], width, height)
        return default

    def getIDs(self):
        with open('plot_ids.binary', 'rb') as f:
            px, py, wx, wy = struct.unpack('iidd', f.read(4*2 + 8*2))
            ids = np.zeros((py, px), dtype=int)
            for i in range(py):
                ids[i] = struct.unpack('{}i'.format(px), f.read(4*px))
        self.ids = ids

    def generatePlot(self):
        t = Thread(target=self.makePlot)
        t.start()
        t.join()

    def makePlot(self):

        cv = self.currentView = copy.deepcopy(self.activeView)

        # Generate plot.xml
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

        self.getIDs()

    def undo(self):
        if self.previousViews:
            self.subsequentViews.append(copy.deepcopy(self.currentView))
            self.activeView = self.previousViews.pop()
            self.generatePlot()

    def redo(self):
        if self.subsequentViews:
            self.storeCurrent()
            self.activeView = self.subsequentViews.pop()
            self.generatePlot()

    def storeCurrent(self):
        self.previousViews.append(copy.deepcopy(self.currentView))


class PlotView():
    def __init__(self, origin, width, height):

        self.origin = origin
        self.width = width + (width * 0.005)
        self.height = height + (height * 0.005)

        self.hRes = 600
        self.vRes = 600
        self.aspectLock = True

        self.basis = 'xy'
        self.colorby = 'material'

        self.cells = self.getDomains('geometry.xml', 'cell')
        self.materials = self.getDomains('materials.xml', 'material')

        self.masking = True
        self.maskBackground = (0,0,0)
        self.highlighting = False
        self.highlightBackground = (80, 80, 80)
        self.highlightAlpha = 0.5
        self.highlightSeed = 1
        self.plotBackground = (50, 50, 50)

    def __eq__(self, other):
        if isinstance(other, PlotView):
            return self.__dict__ == other.__dict__

    def __ne__(self, other):
        if isinstance(other, PlotView):
            return self.__dict__ != other.__dict__

    def getDomains(self, file, type_):

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
            domain = Domain(id, name, color, masked, highlighted)
            domains[id] = domain

        return domains


class Domain():
    def __init__(self, id, name, color=None, masked=False, highlighted=False):

        self.id = id
        self.name = name
        self.color = color
        self.masked = masked
        self.highlighted = highlighted

    def __repr__(self):
        return (f"id: {self.id} \nname: {self.name} \ncolor: {self.color} \
                \nmask: {self.masked} \nhighlight: {self.highlighted}\n\n")

    def __eq__(self, other):
        if isinstance(other, Domain):
            return self.__dict__ == other.__dict__


class DomainTableModel(QAbstractTableModel):
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

        elif role == Qt.TextAlignmentRole:
            if column in (MASK, HIGHLIGHT, COLOR):
                return int(Qt.AlignCenter | Qt.AlignVCenter)
            else:
                return int(Qt.AlignLeft | Qt.AlignVCenter)

        elif role == Qt.BackgroundColorRole:
            if column == COLOR:
                if domain.color is not None:
                    return QColor.fromRgb(*domain.color)

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
                headers = ['ID', 'Name', 'Color', 'RGB', 'Mask', 'Highlight']
                return headers[section]
            return int(section + 1)

        return None

    def flags(self, index):

        if not index.isValid():
            return Qt.ItemIsEnabled

        elif index.column() in (MASK, HIGHLIGHT):
            return Qt.ItemFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable |
                                Qt.ItemIsSelectable)
        elif index.column() == NAME:
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
        elif column in (MASK, HIGHLIGHT):
            return QSize(fm.width("XXXXXXX"), fm.height())
        else:
            return QItemDelegate.sizeHint(self, option, index)

    def createEditor(self, parent, option, index):

        if index.column() == COLOR:
            dialog = QColorDialog(parent)
            return dialog
        else:
            return QItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, editor, index):

        if index.column() == COLOR:
            color = index.data(Qt.BackgroundColorRole)
            editor.setCurrentColor(color)
        elif index.column() == NAME:
            text = index.data(Qt.DisplayRole)
            if text != '--':
                editor.setText(text)

    def editorEvent(self, event, model, option, index):

        if index.column() == COLOR:
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
        else:
            QItemDelegate.setModelData(self, editor, model, index)
