#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, openmc, copy, struct
import numpy as np
import xml.etree.ElementTree as ET
from threading import Thread

class PlotModel():
    def __init__(self):

        self.cells = self.getCells()
        self.materials = self.getMaterials()

        # Cell/Material ID by coordinates
        self.ids = None

        # Read geometry.xml
        self.geom = openmc.Geometry.from_xml('geometry.xml')

        # OpenMC Cells/Materials
        self.modelCells = self.geom.get_all_cells()
        self.modelMaterials = self.geom.get_all_materials()

        self.previousPlots = []
        self.subsequentPlots = []
        self.defaultPlot = self.getDefaultPlot()
        self.currentPlot = copy.deepcopy(self.defaultPlot)
        self.activePlot = copy.deepcopy(self.defaultPlot)

    def getCells(self):

        # Read geometry.xml
        celldoc = ET.parse('geometry.xml')
        cellroot = celldoc.getroot()

        # Create dictionary of cells
        cells = {}
        for cell in cellroot.findall('cell'):
            attr = {}
            id = cell.attrib['id']
            if 'name' in cell.attrib:
                attr['name'] = cell.attrib['name']
            else:
                attr['name'] = None
            attr['color'] = None
            attr['masked'] = False
            attr['highlighted'] = False
            cells[id] = attr

        return cells

    def getMaterials(self):

        # Read materials.xml
        matdoc = ET.parse('materials.xml')
        matroot = matdoc.getroot()

        # Create dictionary of materials
        materials = {}
        for mat in matroot.findall('material'):
            attr = {}
            id = mat.attrib['id']
            if 'name' in mat.attrib:
                attr['name'] = mat.attrib['name']
            else:
                attr['name'] = None
            attr['color'] = None
            attr['masked'] = False
            attr['highlighted'] = False
            materials[id] = attr

        return materials

    def getIDs(self):

        with open('plot_ids.binary', 'rb') as f:
            px, py, wx, wy = struct.unpack('iidd', f.read(4*2 + 8*2))
            ids = np.zeros((py, px), dtype=int)
            for i in range(py):
                ids[i] = struct.unpack('{}i'.format(px), f.read(4*px))

        return ids

    def getDefaultPlot(self):

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

        if  lower_left[2] != -np.inf and upper_right[2] != np.inf:
            zcenter = (upper_right[2] + lower_left[2])/2
        else:
            zcenter = 0.00

        # Generate default plot values
        default = {'xOr': xcenter, 'yOr': ycenter, 'zOr': zcenter,
                   'colorby': 'material', 'basis': 'xy',
                   'width': width + 2, 'height': height + 2,
                   'hRes': 600, 'vRes': 600, 'aspectlock': True,
                   'cells': copy.deepcopy(self.cells),
                   'materials': copy.deepcopy(self.materials),
                   'mask': True, 'maskbg': (0, 0, 0),
                   'highlight': False, 'highlightbg': (80, 80, 80),
                   'highlightalpha': 0.5, 'highlightseed': 1,
                   'plotbackground': (50, 50, 50)}

        return default

    def generatePlot(self):

        t = Thread(target=self.makePlot)
        t.start()
        t.join()

    def makePlot(self):

        self.currentPlot = copy.deepcopy(self.activePlot)

        ap = self.activePlot

        # Generate plot.xml
        plot = openmc.Plot()
        plot.filename = 'plot'
        plot.color_by = ap['colorby']
        plot.basis = ap['basis']
        plot.origin = (ap['xOr'], ap['yOr'], ap['zOr'])
        plot.width = (ap['width'], ap['height'])
        plot.pixels = (ap['hRes'], ap['vRes'])
        plot.background = ap['plotbackground']

        # Cell Colors
        cell_colors = {}
        for id, attr in ap['cells'].items():
            if attr['color']:
                cell_colors[self.modelCells[int(id)]] = attr['color']

        # Material Colors
        mat_colors = {}
        for id, attr in ap['materials'].items():
            if attr['color']:
                mat_colors[self.modelMaterials[int(id)]] = attr['color']

        if ap['colorby'] == 'cell':
            plot.colors = cell_colors
        else:
            plot.colors = mat_colors

        # Masking options
        if ap['mask']:
            cell_mask_components = []
            for cell, attr in ap['cells'].items():
                if not attr['masked']:
                    cell_mask_components.append(self.modelCells[int(cell)])
            material_mask_compenents = []
            for mat, attr in ap['materials'].items():
                if not attr['masked']:
                    material_mask_compenents.append(self.modelMaterials[int(mat)])
            if ap['colorby'] == 'cell':
                plot.mask_components = cell_mask_components
            else:
                plot.mask_components = material_mask_compenents
            plot.mask_background = ap['maskbg']

        # Highlight options
        if ap['highlight']:
            highlighted_cells = []
            for cell, attr in ap['cells'].items():
                if attr['highlighted']:
                    highlighted_cells.append(self.modelCells[int(cell)])
            highlighted_materials = []
            for mat, attr in ap['materials'].items():
                if attr['highlighted']:
                    highlighted_materials.append(self.modelMaterials[int(mat)])
            if ap['colorby'] == 'cell':
                domains = highlighted_cells
            else:
                domains = highlighted_materials
            background = ap['highlightbg']
            alpha = ap['highlightalpha']
            seed = ap['highlightseed']

            plot.highlight_domains(self.geom, domains, seed, alpha, background)

        # Generate plot.xml
        plots = openmc.Plots([plot])
        plots.export_to_xml()
        openmc.plot_geometry()

        self.ids = self.getIDs()

    def undo(self):
        self.subsequentPlots.append(copy.deepcopy(self.currentPlot))
        self.activePlot = self.previousPlots.pop()
        self.generatePlot()

    def redo(self):
        self.storeCurrent()
        self.activePlot = self.subsequentPlots.pop()
        self.generatePlot()

    def storeCurrent(self):
        self.previousPlots.append(copy.deepcopy(self.currentPlot))
