#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, openmc, copy, struct
import numpy as np
import xml.etree.ElementTree as ET
from threading import Thread

class PlotModel():
    def __init__(self):

        # Read geometry.xml
        self.geom = openmc.Geometry.from_xml('geometry.xml')

        # Retrieve OpenMC Cells/Materials
        self.modelCells = self.geom.get_all_cells()
        self.modelMaterials = self.geom.get_all_materials()

        # Cell/Material ID by coordinates
        self.ids = None

        self.previousPlots = []
        self.subsequentPlots = []
        self.defaultPlot = self.getDefaultPlot()
        self.currentPlot = copy.deepcopy(self.defaultPlot)
        self.activePlot = copy.deepcopy(self.defaultPlot)

    def getDomains(self, file, type_):
        """ Return cells/materials from .xml files """

        doc = ET.parse(file)
        root = doc.getroot()

        domains = {}
        for dom in root.findall(type_):
            attr ={}
            id = dom.attrib['id']
            if 'name' in dom.attrib:
                attr['name'] = dom.attrib['name']
            else:
                attr['name'] = None
            attr['color'] = None
            attr['masked'] = False
            attr['highlighted'] = False
            domains[id] = attr

        return domains

    def getDefaultPlot(self):
        """ Return default plot for given geometry """

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
                   'cells': self.getDomains('geometry.xml', 'cell'),
                   'materials': self.getDomains('materials.xml', 'material'),
                   'mask': True, 'maskbg': (0, 0, 0),
                   'highlight': False, 'highlightbg': (80, 80, 80),
                   'highlightalpha': 0.5, 'highlightseed': 1,
                   'plotbackground': (50, 50, 50)}

        return default

    def getIDs(self):

        with open('plot_ids.binary', 'rb') as f:
            px, py, wx, wy = struct.unpack('iidd', f.read(4*2 + 8*2))
            ids = np.zeros((py, px), dtype=int)
            for i in range(py):
                ids[i] = struct.unpack('{}i'.format(px), f.read(4*px))

        return ids

    def generatePlot(self):

        t = Thread(target=self.makePlot)
        t.start()
        t.join()

    def makePlot(self):

        cp = self.currentPlot = copy.deepcopy(self.activePlot)

        # Generate plot.xml
        plot = openmc.Plot()
        plot.filename = 'plot'
        plot.color_by = cp['colorby']
        plot.basis = cp['basis']
        plot.origin = (cp['xOr'], cp['yOr'], cp['zOr'])
        plot.width = (cp['width'], cp['height'])
        plot.pixels = (cp['hRes'], cp['vRes'])
        plot.background = cp['plotbackground']

        # Determine domain type and source
        if cp['colorby'] == 'cell':
            domain = 'cells'
            source = self.modelCells
        else:
            domain = 'materials'
            source = self.modelMaterials

        # Custom Colors
        plot.colors = {}
        for id, attr in cp[domain].items():
            if attr['color']:
                plot.colors[source[int(id)]] = attr['color']

        # Masking options
        if cp['mask']:
            plot.mask_components = []
            for id, attr in cp[domain].items():
                if not attr['masked']:
                    plot.mask_components.append(source[int(id)])

            plot.mask_background = cp['maskbg']

        # Highlighting options
        if cp['highlight']:
            domains = []
            for id, attr in cp[domain].items():
                if attr['highlighted']:
                    domains.append(source[int(id)])

            background = cp['highlightbg']
            alpha = cp['highlightalpha']
            seed = cp['highlightseed']

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
