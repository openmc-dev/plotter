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

        if  lower_left[2] != -np.inf and upper_right[2] != np.inf:
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

        return ids

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

        self.ids = self.getIDs()

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
        self.width = width + 2
        self.height = height + 2

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
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
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
            domain = Domain(id, type_, name, color, masked, highlighted)
            domains[domain.id] = domain

        return domains


class Domain():
    def __init__(self, id, type_, name, color, masked, highlighted):

        self.id = id
        self.type_ = type_
        self.name = name
        self.color = color
        self.masked = masked
        self.highlighted = highlighted

    def __repr__(self):
        return f"{self.type_}: {self.id}"

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return self.__dict__ != other.__dict__
