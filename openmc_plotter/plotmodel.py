from __future__ import annotations
from ast import literal_eval
from collections import defaultdict
import copy
from ctypes import c_int32, c_char_p
import hashlib
import itertools
import pickle
import threading
from typing import Literal, Tuple, Optional, Dict

from PySide6.QtWidgets import QItemDelegate, QColorDialog, QLineEdit, QMessageBox
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSize, QEvent
from PySide6.QtGui import QColor
import openmc
import openmc.lib
import numpy as np

from . import __version__
from .statepointmodel import StatePointModel
from .plot_colors import random_rgb

ID, NAME, COLOR, COLORLABEL, MASK, HIGHLIGHT = range(6)

_VOID_REGION = -1
_NOT_FOUND = -2
_OVERLAP = -3

_MODEL_PROPERTIES = ('temperature', 'density')
_PROPERTY_INDICES = {'temperature': 0, 'density': 1}

_REACTION_UNITS = 'reactions/source'
_PRODUCTION_UNITS = 'particles/source'
_ENERGY_UNITS = 'eV/source'

_REACTION_UNITS_VOL = 'reactions/cm³/source'
_PRODUCTION_UNITS_VOL = 'particles/cm³/source'
_ENERGY_UNITS_VOL = 'eV/cm³/source'


_SPATIAL_FILTERS = (openmc.UniverseFilter,
                    openmc.MaterialFilter,
                    openmc.CellFilter,
                    openmc.DistribcellFilter,
                    openmc.CellInstanceFilter,
                    openmc.MeshFilter)

_PRODUCTIONS = ('delayed-nu-fission', 'prompt-nu-fission', 'nu-fission',
               'nu-scatter', 'H1-production', 'H2-production',
               'H3-production', 'He3-production', 'He4-production')
_ENERGY_SCORES = {'heating', 'heating-local', 'kappa-fission',
                  'fission-q-prompt', 'fission-q-recoverable',
                  'damage-energy'}

_SCORE_UNITS = {p: _PRODUCTION_UNITS for p in _PRODUCTIONS}
_SCORE_UNITS['flux'] = 'particle-cm/source'
_SCORE_UNITS['current'] = 'particle/source'
_SCORE_UNITS['events'] = 'events/source'
_SCORE_UNITS['inverse-velocity'] = 'particle-s/source'
_SCORE_UNITS['decay-rate'] = 'particle/s/source'
_SCORE_UNITS.update({s: _ENERGY_UNITS for s in _ENERGY_SCORES})

_SCORE_UNITS_VOL = {p: _PRODUCTION_UNITS_VOL for p in _PRODUCTIONS}
_SCORE_UNITS_VOL['flux'] = 'particle/cm²/source'
_SCORE_UNITS_VOL['current'] = 'particle/cm³/source'
_SCORE_UNITS_VOL['events'] = 'events/cm³/source'
_SCORE_UNITS_VOL['inverse-velocity'] = 'particle-s/cm³/source'
_SCORE_UNITS_VOL['decay-rate'] = 'particle/s/cm³/source'
_SCORE_UNITS.update({s: _ENERGY_UNITS_VOL for s in _ENERGY_SCORES})


_TALLY_VALUES = {'Mean': 'mean',
                 'Std. Dev.': 'std_dev',
                 'Rel. Error': 'rel_err'}

TallyValueType = Literal['mean', 'std_dev', 'rel_err']


def hash_file(path):
    # return the md5 hash of a file
    h = hashlib.md5()
    with path.open('rb') as file:
        chunk = 0
        while chunk != b'':
            # read 32768 bytes at a time
            chunk = file.read(32768)
            h.update(chunk)
    return h.hexdigest()


def hash_model(model_path):
    """Get hash values for materials.xml and geometry.xml (or model.xml)"""
    if model_path.is_file():
        mat_xml_hash = hash_file(model_path)
        geom_xml_hash = ""
    elif (model_path / 'model.xml').exists():
        mat_xml_hash = hash_file(model_path / 'model.xml')
        geom_xml_hash = ""
    else:
        mat_xml_hash = hash_file(model_path / 'materials.xml')
        geom_xml_hash = hash_file(model_path / 'geometry.xml')
    return mat_xml_hash, geom_xml_hash


class PlotModel:
    """Geometry and plot settings for OpenMC Plot Explorer model

    Parameters
    ----------
    use_settings_pkl : bool
        If True, use plot_settings.pkl file to reload settings
    model_path : pathlib.Path
        Path to model XML file or directory
    default_res : int
        Default resolution as the number of pixels in each direction

    Attributes
    ----------
    geom : openmc.Geometry
        OpenMC Geometry of the model
    modelCells : collections.OrderedDict
        Dictionary mapping cell IDs to openmc.Cell instances
    modelMaterials : collections.OrderedDict
        Dictionary mapping material IDs to openmc.Material instances
    ids : NumPy int array (v_res, h_res, 1)
        Mapping of plot coordinates to cell/material ID by pixel
    ids_map : NumPy int32 array (v_res, h_res, 3)
        Mapping of cell and material ids
    properties : Numpy float array (v_res, h_res, 3)
        Mapping of cell temperatures and material densities
    image : NumPy int array (v_res, h_res, 3)
        The current RGB image data
    statepoint : StatePointModel
        Simulation data model used to display tally results
    applied_filters : tuple of ints
        IDs of the applied filters for the displayed tally
    previousViews : list of PlotView instances
        List of previously created plot view settings used to undo
        changes made in plot explorer
    subsequentViews : list of PlotView instances
        List of undone plot view settings used to redo changes made
        in plot explorer
    sourceSitesTolerance : float
        Tolerance for source site plotting (default 0.1 cm)
    sourceSitesColor : tuple of 3 int
        RGB color for source site plotting (default blue)
    sourceSitesVisible : bool
        Whether to plot source sites (default True)
    sourceSites :  Source sites to plot
        Set of source locations to plot
    defaultView : PlotView
        Default settings for given geometry
    currentView : PlotView
        Currently displayed plot settings in plot explorer
    activeView : PlotView
        Active state of settings in plot explorer, which may or may not
        have unapplied changes
    """

    def __init__(self, use_settings_pkl, model_path, default_res):
        """ Initialize PlotModel class attributes """

        # Retrieve OpenMC Cells/Materials
        self.modelCells = openmc.lib.cells
        self.modelMaterials = openmc.lib.materials
        self.max_universe_levels = openmc.lib._coord_levels()

        # Cell/Material ID by coordinates
        self.ids = None

        # Return values from id_map and property_map
        self.ids_map = None
        self.properties = None

        self.version = __version__

        # default statepoint value
        self._statepoint = None
        # default tally/filter info
        self.appliedFilters = ()
        self.appliedScores = ()
        self.appliedNuclides = ()

        self.previousViews = []
        self.subsequentViews = []

        self.defaultView = self.getDefaultView(default_res)

        # Source site defaults
        self.sourceSitesApplyTolerance = False
        self.sourceSitesTolerance = 0.1 # cm
        self.sourceSitesColor = (0, 0, 255)
        self.sourceSitesVisible = True
        self.sourceSites = None

        if model_path.is_file():
            settings_pkl = model_path.with_name('plot_settings.pkl')
        else:
            settings_pkl = model_path / 'plot_settings.pkl'

        if use_settings_pkl and settings_pkl.is_file():
            with settings_pkl.open('rb') as file:
                try:
                    data = pickle.load(file)
                except AttributeError:
                    msg_box = QMessageBox()
                    msg = "WARNING: previous plot settings are in an incompatible format. " +\
                          "They will be ignored."
                    msg_box.setText(msg)
                    msg_box.setIcon(QMessageBox.Warning)
                    msg_box.setStandardButtons(QMessageBox.Ok)
                    msg_box.exec()
                    self.currentView = copy.deepcopy(self.defaultView)

                else:
                    restore_domains = False

                    # check GUI version
                    if data['version'] != self.version:
                        print("WARNING: previous plot settings are for a different "
                            "version of the GUI. They will be ignored.")
                        wrn_msg = "Existing version: {}, Current GUI version: {}"
                        print(wrn_msg.format(data['version'], self.version))
                        view = None
                    else:
                        view = data['currentView']

                        # get materials.xml and geometry.xml hashes to
                        # restore additional settings if possible
                        mat_xml_hash, geom_xml_hash = hash_model(model_path)
                        if mat_xml_hash == data['mat_xml_hash'] and \
                            geom_xml_hash == data['geom_xml_hash']:
                            restore_domains = True

                        # restore statepoint file
                        try:
                            self.statepoint = data['statepoint']
                        except OSError:
                            msg_box = QMessageBox()
                            msg = "Could not open statepoint file: \n\n {} \n"
                            msg_box.setText(msg.format(self.model.statepoint.filename))
                            msg_box.setIcon(QMessageBox.Warning)
                            msg_box.setStandardButtons(QMessageBox.Ok)
                            msg_box.exec()
                            self.statepoint = None

                    self.currentView = PlotView(restore_view=view,
                                                restore_domains=restore_domains,
                                                default_res=default_res)

        else:
            self.currentView = copy.deepcopy(self.defaultView)

        self.activeView = copy.deepcopy(self.currentView)

    def openStatePoint(self, filename):
        self.statepoint = StatePointModel(filename, open_file=True)

    @property
    def statepoint(self):
        return self._statepoint

    @statepoint.setter
    def statepoint(self, statepoint):
        if statepoint is None:
            self._statepoint = None
        elif isinstance(statepoint, StatePointModel):
            self._statepoint = statepoint
        elif isinstance(statepoint, str):
            self._statepoint = StatePointModel(statepoint, open_file=True)
        else:
            raise TypeError("Invalid statepoint object")

        if self._statepoint and not self._statepoint.is_open:
            self._statepoint.open()

    def getDefaultView(self, default_res):
        """ Generates default PlotView instance for OpenMC geometry

        Centers plot view origin in every dimension if possible. Defaults
        to xy basis, with height and width to accomodate full size of
        geometry. Defaults to (0, 0, 0) origin with width and heigth of
        25 if geometry bounding box cannot be generated.

        Parameters
        ----------
        default_res : int
            Default resolution as the number of pixels in each direction

        Returns
        -------
        default : PlotView instance
            PlotView instance with default view settings
        """

        lower_left, upper_right = openmc.lib.global_bounding_box()

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

        default = PlotView([xcenter, ycenter, zcenter], width, height,
                           default_res=default_res)
        return default

    def resetColors(self):
        """ Reset colors to those generated in the default view """
        self.activeView.cells = self.defaultView.cells
        self.activeView.materials = self.defaultView.materials

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
        # update/call maps under 2 circumstances
        #   1. this is the intial plot (ids_map/properties are None)
        #   2. The active (desired) view differs from the current view parameters
        if (self.currentView.view_params != self.activeView.view_params) or \
            (self.ids_map is None) or (self.properties is None):
            # get ids from the active (desired) view
            self.ids_map = openmc.lib.id_map(self.activeView.view_params)
            self.properties = openmc.lib.property_map(self.activeView.view_params)

        # update current view
        cv = self.currentView = copy.deepcopy(self.activeView)

        # set model ids based on domain
        if cv.colorby == 'cell':
            self.ids = self.cell_ids
            domain = cv.cells
            source = self.modelCells
        else:
            self.ids = self.mat_ids
            domain = cv.materials
            source = self.modelMaterials

        # generate colors if not present
        for cell_id, cell in cv.cells.items():
            if cell.color is None:
                cv.cells.set_color(cell_id, random_rgb())

        for mat_id, mat in cv.materials.items():
            if mat.color is None:
                cv.material.set_color(mat_id, random_rgb())

        # construct image data
        domain[_OVERLAP] = DomainView(_OVERLAP, "Overlap", cv.overlap_color)
        domain[_NOT_FOUND] = DomainView(_NOT_FOUND, "Not Found", cv.domainBackground)
        u, inv = np.unique(self.ids, return_inverse=True)
        image = np.array([domain[id].color for id in u])[inv]
        image.shape = (cv.v_res, cv.h_res, 3)

        if cv.masking:
            for id, dom in domain.items():
                if dom.masked:
                    image[self.ids == int(id)] = cv.maskBackground

        if cv.highlighting:
            for id, dom in domain.items():
                if dom.highlight:
                    image[self.ids == int(id)] = cv.highlightBackground

        # set model image
        self.image = image

        # tally data
        self.tally_data = None

        self.properties[self.properties < 0.0] = np.nan

        self.temperatures = self.properties[..., _PROPERTY_INDICES['temperature']]
        self.densities = self.properties[..., _PROPERTY_INDICES['density']]

        minmax = {}
        for prop in _MODEL_PROPERTIES:
            idx = _PROPERTY_INDICES[prop]
            prop_data = self.properties[:, :, idx]
            minmax[prop] = (np.min(np.nan_to_num(prop_data)),
                            np.max(np.nan_to_num(prop_data)))

        self.activeView.data_minmax = minmax

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

    def getExternalSourceSites(self, n=100):
        """Plot source sites from a source file
        """
        if n == 0:
            self.source_sites = None
            return
        sites = openmc.lib.sample_external_source(n)
        self.sourceSites = np.array([s.r for s in sites[:n]], dtype=float)

    def storeCurrent(self):
        """ Add current view to previousViews list """
        self.previousViews.append(copy.deepcopy(self.currentView))

    def create_tally_image(self, view: Optional[PlotView] = None):
        """
        Parameters
        ----------
        view : PlotView
            View used to set bounds of the tally data

        Returns
        -------
        tuple
            image data (numpy.ndarray), data extents (optional),
            data_min_value (float), data_max_value (float),
            data label (str)
        """
        if view is None:
            view = self.currentView

        tally_id = view.selectedTally

        scores = self.appliedScores
        nuclides = self.appliedNuclides

        tally_selected = view.selectedTally is not None
        tally_visible = view.tallyDataVisible
        visible_selection = scores and nuclides

        if not tally_selected or not tally_visible or not visible_selection:
            return (None, None, None, None, None)

        tally = self.statepoint.tallies[tally_id]

        tally_value = _TALLY_VALUES[view.tallyValue]

        # check score units
        units = {_SCORE_UNITS.get(score, _REACTION_UNITS) for score in scores}

        if len(units) != 1:
            msg_box = QMessageBox()
            unit_str = " ".join(units)
            msg = "The scores selected have incompatible units:\n"
            for unit in units:
                msg += "  - {}\n".format(unit)
            msg_box.setText(msg)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec()
            return (None, None, None, None, None)

        units_out = list(units)[0]

        contains_distribcell = tally.contains_filter(openmc.DistribcellFilter)
        contains_cellinstance = tally.contains_filter(openmc.CellInstanceFilter)

        if tally.contains_filter(openmc.MeshFilter):
            # Check for volume normalization in order to change units
            if view.tallyVolumeNorm:
                units_out = _SCORE_UNITS_VOL.get(scores[0], _REACTION_UNITS_VOL)

            if tally_value == 'rel_err':
                # Get both the std. dev. data and mean data to create the
                # relative error data
                mean_data = self._create_tally_mesh_image(
                    tally, 'mean', scores, nuclides, view)[0]
                std_dev_data = self._create_tally_mesh_image(
                    tally, 'std_dev', scores, nuclides, view)[0]
                with np.errstate(divide='ignore', invalid='ignore'):
                    image_data = 100.0 * std_dev_data / mean_data
                if np.isnan(image_data).all():
                    data_min, data_max = 0., 1.
                else:
                    data_min = np.nanmin(image_data)
                    data_max = np.nanmax(image_data)
                return image_data, None, data_min, data_max, '% error'

            else:
                image = self._create_tally_mesh_image(tally,
                                                      tally_value,
                                                      scores,
                                                      nuclides,
                                                      view)
                return image + (units_out,)
        elif contains_distribcell or contains_cellinstance:
            if tally_value == 'rel_err':
                mean_data = self._create_distribcell_image(
                    tally, 'mean', scores, nuclides, contains_cellinstance)
                std_dev_data = self._create_distribcell_image(
                    tally, 'std_dev', scores, nuclides)
                image_data = 100 * np.divide(
                    std_dev_data[0], mean_data[0],
                    out=np.zeros_like(mean_data[0]),
                    where=mean_data != 0
                )
                data_min = np.min(image_data)
                data_max = np.max(image_data)
                return image_data, None, data_min, data_max, '% error'
            else:
                image = self._create_distribcell_image(
                    tally, tally_value, scores, nuclides, contains_cellinstance)
                return image + (units_out,)
        else:
            # same as above, get the std. dev. data
            # and mean date to produce the relative error data
            if tally_value == 'rel_err':
                mean_data = self._create_tally_domain_image(tally,
                                                            'mean',
                                                            scores,
                                                            nuclides)
                std_dev_data = self._create_tally_domain_image(tally,
                                                           'std_dev',
                                                           scores,
                                                           nuclides)
                image_data = 100 * np.divide(std_dev_data[0],
                                             mean_data[0],
                                             out=np.zeros_like(mean_data[0]),
                                             where=mean_data != 0)
                # adjust for NaNs in bins without tallies
                image_data = np.nan_to_num(image_data,
                                           nan=0.0,
                                           posinf=0.0,
                                           neginf=0.0)
                extents = mean_data[1]
                data_min = np.min(image_data)
                data_max = np.max(image_data)
                return image_data, extents, data_min, data_max, '% error'
            else:
                image = self._create_tally_domain_image(tally,
                                                        tally_value,
                                                        scores,
                                                        nuclides)
                return image + (units_out,)

    def _create_tally_domain_image(self, tally, tally_value, scores, nuclides, view=None):
        # data resources used throughout
        if view is None:
            view = self.currentView

        data = tally.get_reshaped_data(tally_value)
        data_out = np.full(self.ids.shape, -1.0)

        def _do_op(array, tally_value, ax=0):
            if tally_value == 'mean':
                return np.sum(array, axis=ax)
            elif tally_value == 'std_dev':
                return np.sqrt(np.sum(array**2, axis=ax))

        # data structure for tracking which spatial
        # filter bins are enabled
        spatial_filter_bins = defaultdict(list)
        n_spatial_filters = 0

        for tally_filter in tally.filters:
            if tally_filter in self.appliedFilters:
                selected_bins = self.appliedFilters[tally_filter]

                if type(tally_filter) in _SPATIAL_FILTERS:
                    spatial_filter_bins[tally_filter] = selected_bins
                    n_spatial_filters += 1
                else:
                    slc = [slice(None)] * len(data.shape)
                    slc[n_spatial_filters] = selected_bins
                    slc = tuple(slc)
                    data = _do_op(data[slc], tally_value, n_spatial_filters)
            else:
                data[:] = 0.0
                data = _do_op(data, tally_value, n_spatial_filters)

        # filter by selected scores
        selected_scores = []
        for idx, score in enumerate(tally.scores):
            if score in scores:
                selected_scores.append(idx)
        data = _do_op(data[..., np.array(selected_scores)], tally_value, -1)

        # filter by selected nuclides
        selected_nuclides = []
        for idx, nuclide in enumerate(tally.nuclides):
            if nuclide in nuclides:
                selected_nuclides.append(idx)
        data = _do_op(data[..., np.array(selected_nuclides)], tally_value, -1)

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
            mask = np.full(self.ids.shape, True, dtype=bool)

            for tally_filter, bin_idx in zip(spatial_filters, bin_indices):
                bin = tally_filter.bins[bin_idx]
                if isinstance(tally_filter, openmc.CellFilter):
                    mask &= self.cell_ids == bin
                elif isinstance(tally_filter, openmc.MaterialFilter):
                    mask &= self.mat_ids == bin
                elif isinstance(tally_filter, openmc.UniverseFilter):
                    # get the statepoint summary
                    univ_cells = self.statepoint.universes[bin].cells
                    for cell in univ_cells:
                        mask &= self.cell_ids == cell

            # set image data values
            data_out[mask] = tally_val

        # mask out invalid values
        image_data = np.ma.masked_where(data_out < 0.0, data_out)

        return image_data, None, data_min, data_max

    def _create_distribcell_image(self, tally, tally_value, scores, nuclides, cellinstance=False):
        # Get flattened array of tally results
        data = tally.get_values(scores=scores, nuclides=nuclides, value=tally_value)
        data = data.flatten()

        # Create an empty array of appropriate shape for image
        image_data = np.full_like(self.ids, np.nan, dtype=float)

        # Determine mapping of cell IDs to list of (instance, tally value).
        if cellinstance:
            f = tally.find_filter(openmc.CellInstanceFilter)
            cell_id_to_inst_value = defaultdict(list)
            for value, (cell_id, instance) in zip(data, f.bins):
                cell_id_to_inst_value[cell_id].append((instance, value))
        else:
            f = tally.find_filter(openmc.DistribcellFilter)
            cell_id_to_inst_value = {f.bins[0]: list(enumerate(data))}

        for cell_id, value_list in cell_id_to_inst_value.items():
            # Get mask for each relevant cell
            cell_id_mask = (self.cell_ids == cell_id)

            # For each cell, iterate over instances and corresponding tally
            # values and set any matching pixels
            for instance, value in value_list:
                instance_mask = (self.instances == instance)
                image_data[cell_id_mask & instance_mask] = value

        data_min = np.min(data)
        data_max = np.max(data)
        image_data = np.ma.masked_where(image_data < 0.0, image_data)

        return image_data, None, data_min, data_max

    def _create_tally_mesh_image(
            self, tally: openmc.Tally, tally_value: TallyValueType,
            scores: Tuple[str], nuclides: Tuple[str], view: PlotView = None
        ):
        # some variables used throughout
        if view is None:
            view = self.currentView

        mesh_filter = tally.find_filter(openmc.MeshFilter)
        mesh = mesh_filter.mesh

        def _do_op(array, tally_value, ax=0):
            if tally_value == 'mean':
                return np.sum(array, axis=ax)
            elif tally_value == 'std_dev':
                return np.sqrt(np.sum(array**2, axis=ax))

        # start with reshaped data
        data = tally.get_reshaped_data(tally_value)

        # move mesh axes to the end of the filters
        filter_idx = [type(filter) for filter in tally.filters].index(openmc.MeshFilter)
        data = np.moveaxis(data, filter_idx, -1)

        # sum over the rest of the tally filters
        for tally_filter in tally.filters:
            if type(tally_filter) == openmc.MeshFilter:
                continue

            selected_bins = self.appliedFilters[tally_filter]
            if selected_bins:
                # sum filter data for the selected bins
                data = data[np.array(selected_bins)].sum(axis=0)
            else:
                # if the filter is completely unselected,
                # set all of its data to zero and remove the axis
                data[:] = 0.0
                data = _do_op(data, tally_value)

        # filter by selected nuclides
        if not nuclides:
            data = 0.0

        selected_nuclides = []
        for idx, nuclide in enumerate(tally.nuclides):
            if nuclide in nuclides:
                selected_nuclides.append(idx)
        data = _do_op(data[np.array(selected_nuclides)], tally_value)

        # filter by selected scores
        if not scores:
            data = 0.0

        selected_scores = []
        for idx, score in enumerate(tally.scores):
            if score in scores:
                selected_scores.append(idx)
        data = _do_op(data[np.array(selected_scores)], tally_value)

        # Account for mesh filter translation
        if mesh_filter.translation is not None:
            t = mesh_filter.translation
            origin = (view.origin[0] - t[0], view.origin[1] - t[1], view.origin[2] - t[2])
        else:
            origin = view.origin

        # Get mesh bins from openmc.lib
        mesh_cpp = openmc.lib.meshes[mesh.id]
        mesh_bins = mesh_cpp.get_plot_bins(
            origin=origin,
            width=(view.width, view.height),
            basis=view.basis,
            pixels=(view.h_res, view.v_res),
        )

        # Apply volume normalization
        if view.tallyVolumeNorm:
            data /= mesh_cpp.volumes

        # set image data
        image_data = np.full_like(self.ids, np.nan, dtype=float)
        mask = (mesh_bins >= 0)
        image_data[mask] = data[mesh_bins[mask]]

        # get dataset's min/max
        data_min = np.min(data)
        data_max = np.max(data)

        return image_data, None, data_min, data_max

    @property
    def cell_ids(self):
        return self.ids_map[:, :, 0]

    @property
    def instances(self):
        return self.ids_map[:, :, 1]

    @property
    def mat_ids(self):
        return self.ids_map[:, :, 2]


class ViewParam(openmc.lib.plot._PlotBase):
    """Viewer settings that are needed for _PlotBase and are independent
    of all other plotter/model settings.

    Parameters
    ----------
    origin : 3-tuple of floats
        Origin (center) of plot view
    width: float
        Width of plot view in model units
    height : float
        Height of plot view in model units
    default_res : int
        Default resolution as the number of pixels in each direction

    Attributes
    ----------
    origin : 3-tuple of floats
        Origin (center) of plot view
    width : float
        Width of the plot view in model units
    height : float
        Height of the plot view in model units
    h_res : int
        Horizontal resolution of plot image
    v_res : int
        Vertical resolution of plot image
    basis : {'xy', 'xz', 'yz'}
        The basis directions for the plot
    slice_axis : int
        The axis along which the plot is sliced
    color_overlaps : bool
        Indicator of whether or not overlaps will be shown
    level : int
        The universe level for the plot (default: -1 -> all universes shown)
    """

    def __init__(self, origin=(0, 0, 0), width=10, height=10, default_res=1000):
        """Initialize ViewParam attributes"""
        super().__init__()

        # View Parameters
        self.level = -1
        self.origin = origin
        self.width = width
        self.height = height
        self.h_res = default_res
        self.v_res = default_res
        self.basis = 'xy'
        self.color_overlaps = False

    @property
    def slice_axis(self):
        if self.basis == 'xy':
            return 2
        elif self.basis == 'yz':
            return 0
        else:
            return 1

    @property
    def llc(self):
        if self.basis == 'xy':
            x = self.origin[0] - self.width / 2.0
            y = self.origin[1] - self.height / 2.0
            z = self.origin[2]
        elif self.basis == 'yz':
            x = self.origin[0]
            y = self.origin[1] - self.width / 2.0
            z = self.origin[2] - self.height / 2.0
        else:
            x = self.origin[0] - self.width / 2.0
            y = self.origin[1]
            z = self.origin[2] - self.height / 2.0
        return x, y, z

    @property
    def urc(self):
        if self.basis == 'xy':
            x = self.origin[0] + self.width / 2.0
            y = self.origin[1] + self.height / 2.0
            z = self.origin[2]
        elif self.basis == 'yz':
            x = self.origin[0]
            y = self.origin[1] + self.width / 2.0
            z = self.origin[2] + self.height / 2.0
        else:
            x = self.origin[0] + self.width / 2.0
            y = self.origin[1]
            z = self.origin[2] + self.height / 2.0
        return x, y, z

    def __eq__(self, other):
        return repr(self) == repr(other)

class PlotViewIndependent:
    """View settings for OpenMC plot, independent of the model.

    Attributes
    ----------
    aspectLock : bool
        Indication of whether aspect lock should be maintained to
        prevent image stretching/warping
    colorby : {'cell', 'material', 'temperature', 'density'}
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
    domainBackground : 3-tuple of int
        RGB color to apply to plot background
    overlap_color : 3-tuple of int
        RGB color to apply for cell overlap regions
    domainAlpha : float between 0 and 1
        Alpha value of the geometry plot
    plotVisibile : bool
        Controls visibility of geometry
    outlines: bool
        Controls visibility of geometry outlines
    tallyDataColormap : str
        Name of the colormap used for tally data
    tallyDataVisible : bool
        Indicator for whether or not the tally data is visible
    tallyDataAlpha : float
        Value of the tally image alpha
    tallyDataIndicator : bool
        Indicates whether or not the data indicator is active on the tally colorbar
    tallyDataMin : float
        Minimum scale value for tally data
    tallyDataMax : float
        Minimum scale value for tally data
    tallyDataLogScale : bool
        Indicator of logarithmic scale for tally data
    tallyMaskZeroValues : bool
        Indicates whether or not zero values in tally data should be masked
    clipTallyData: bool
        Indicates whether or not tally data is clipped by the colorbar min/max
    tallyValue : str
        Indicator for what type of value is displayed in plots.
    tallyContours : bool
        Indicates whether or not tallies are displayed as contours
    tallyContourLevels : str
        Number of contours levels or explicit level values
    """

    def __init__(self):
        """Initialize PlotViewIndependent attributes"""
        # Geometry Plot
        self.aspectLock = True
        self.colorby = 'material'
        self.masking = True
        self.maskBackground = (0, 0, 0)
        self.highlighting = False
        self.highlightBackground = (80, 80, 80)
        self.highlightAlpha = 0.5
        self.highlightSeed = 1
        self.domainBackground = (50, 50, 50)
        self.overlap_color = (255, 0, 0)
        self.domainAlpha = 1.0
        self.domainVisible = True
        self.outlines = False
        self.colormaps = {'temperature': 'Oranges', 'density': 'Greys'}
        # set defaults for color dialog
        self.data_minmax = {prop: (0.0, 0.0) for prop in _MODEL_PROPERTIES}
        self.user_minmax = {prop: (0.0, 0.0) for prop in _MODEL_PROPERTIES}
        self.use_custom_minmax = {prop: False for prop in _MODEL_PROPERTIES}
        self.data_indicator_enabled = {prop: False for prop in _MODEL_PROPERTIES}
        self.color_scale_log = {prop: False for prop in _MODEL_PROPERTIES}

        # Tally Viz Settings
        self.tallyDataColormap = 'Spectral'
        self.tallyDataReverseCmap = False
        self.tallyDataVisible = True
        self.tallyDataAlpha = 1.0
        self.tallyDataIndicator = False
        self.tallyDataUserMinMax = False
        self.tallyDataMin = 0.0
        self.tallyDataMax = np.inf
        self.tallyDataLogScale = False
        self.tallyMaskZeroValues = False
        self.tallyVolumeNorm = False
        self.clipTallyData = False
        self.tallyValue = "Mean"
        self.tallyContours = False
        self.tallyContourLevels = ""

    def getDataLimits(self):
        return self.data_minmax

    def getColorLimits(self, property):
        if self.use_custom_minmax[property]:
            return self.user_minmax[property]
        else:
            return self.data_minmax[property]


class PlotView:
    """Setup the view of the model.

    Parameters
    ----------
    origin : 3-tuple of floats
        Origin (center) of plot view
    width : float
        Width of plot view in model units
    height : float
        Height of plot view in model units
    restore_view : PlotView or None
        view object with specified parameters to restore
    restore_domains : bool (optional)
        If True and restore_view is provided, then also restore domain
        properties. Default False.

    Attributes
    ----------
    view_ind : PlotViewIndependent instance
        viewing parameters that are independent of the model
    view_params : ViewParam instance
        view parameters necesary for _PlotBase
    cells : Dict of DomainView instances
        Dictionary of cell view settings by ID
    materials : Dict of DomainView instances
        Dictionary of material view settings by ID
    selectedTally : str
        Label of the currently selected tally
    """

    attrs = ('view_ind', 'view_params', 'cells', 'materials', 'selectedTally')
    plotbase_attrs = ('level', 'origin', 'width', 'height',
                      'h_res', 'v_res', 'basis', 'llc', 'urc', 'color_overlaps')

    def __init__(self, origin=(0, 0, 0), width=10, height=10, restore_view=None,
                 restore_domains=False, default_res=None):
        """Initialize PlotView attributes"""

        if restore_view is not None:
            self.view_ind = copy.copy(restore_view.view_ind)
            self.view_params = copy.copy(restore_view.view_params)
            if default_res is not None:
                p = self.view_params
                p.h_res = default_res
                p.v_res = int(default_res * p.height / p.width)
        else:
            self.view_ind = PlotViewIndependent()
            if default_res is not None:
                self.view_params = ViewParam(origin, width, height, default_res)
            else:
                self.view_params = ViewParam(origin, width, height)

        # Get model domain info
        if restore_domains and restore_view is not None:
            self.cells = restore_view.cells
            self.materials = restore_view.materials
            self.selectedTally = restore_view.selectedTally
        else:
            rng = np.random.RandomState(10)
            self.cells = self.getDomains('cell', rng)
            self.materials = self.getDomains('material', rng)
            self.selectedTally = None

    def __getattr__(self, name):
        if name in self.attrs:
            if name not in self.__dict__:
                raise AttributeError('{} not in PlotView dict'.format(name))
            return self.__dict__[name]
        elif name in self.plotbase_attrs:
            return getattr(self.view_params, name)
        else:
            return getattr(self.view_ind, name)

    def __setattr__(self, name, value):
        if name in self.attrs:
            super().__setattr__(name, value)
        elif name in self.plotbase_attrs:
            setattr(self.view_params, name, value)
        else:
            setattr(self.view_ind, name, value)

    def __hash__(self):
        return hash(self.__dict__.__str__() + self.__str__())

    @staticmethod
    def getDomains(domain_type, rng) -> DomainViewDict:
        """ Return dictionary of domain settings.

        Retrieve cell or material ID numbers and names from .xml files
        and convert to DomainView instances with default view settings.

        Parameters
        ----------
        domain_type : {'cell', 'material'}
            Type of domain to retrieve for dictionary

        Returns
        -------
        domains : Dictionary of DomainView instances
            Dictionary of cell/material DomainView instances keyed by ID
        """

        if domain_type not in ('cell', 'material'):
            raise ValueError("Domain type, {}, requested is neither "
                             "'cell' nor 'material'.".format(domain_type))

        # Get number of domains, functions for ID/name, and dictionary for defaults
        if domain_type == 'cell':
            num_domain = len(openmc.lib.cells)
            get_id = openmc.lib.core._dll.openmc_cell_get_id
            get_name = openmc.lib.core._dll.openmc_cell_get_name
        elif domain_type == 'material':
            num_domain = len(openmc.lib.materials)
            get_id = openmc.lib.core._dll.openmc_material_get_id
            get_name = openmc.lib.core._dll.openmc_material_get_name

        # Sample default colors for each domain
        colors = rng.randint(256, size=(num_domain, 3))

        domain_id_c = c_int32()
        name_c = c_char_p()
        defaults = {}
        for i, color in enumerate(colors):
            # Get ID and name for each domain
            get_id(i, domain_id_c)
            get_name(i, name_c)
            domain_id = domain_id_c.value
            name = name_c.value.decode()

            # Create default domain view for this domain
            defaults[domain_id] = DomainView(domain_id, name, color)

        # always add void to a material domain at the end
        if domain_type == 'material':
            void_id = _VOID_REGION
            defaults[void_id] = DomainView(void_id, "VOID", (255, 255, 255),
                                          False, False)

        return DomainViewDict(defaults)

    def adopt_plotbase(self, view):
        """
        Applies only the geometric aspects of a view to the current view

        Parameters
        ----------

        view : PlotView
            View to take parameters from
        """
        self.origin = view.origin
        self.width = view.width
        self.height = view.height
        self.h_res = view.h_res
        self.v_res = view.v_res
        self.basis = view.basis


class DomainViewDict(dict):
    """Dictionary of domain ID to DomainView objects with shared defaults

    When the active/current view changes in the plotter, this dictionary gets
    deepcopied. To avoid the dictionary being huge for models with lots of
    cells/materials, defaults are stored separately and the key/value pairs in
    this dictionary represent modifications to the default pairs. When an item
    is looked up, if there is no locally modified version we pull the value from
    the defaults dictionary.

    """
    def __init__(self, defaults: Dict[int, DomainView]):
        self.defaults = defaults

    def __getitem__(self, key) -> DomainView:
        if key in self:
            return super().__getitem__(key)
        else:
            # If key is not present, pull it from the defaults
            return self.defaults[key]

    def __deepcopy__(self, memo):
        cls = self.__class__
        obj = cls.__new__(cls)
        memo[id(self)] = obj
        for key, value in self.items():
            obj[key] = copy.deepcopy(value)
        # Shallow copy the defaults dictionary
        obj.defaults = self.defaults
        return obj

    def get_defaults(self, key: int) -> DomainView:
        return self.defaults[key]

    def get_default_color(self, key: int):
        return self.get_defaults(key).color

    def set_name(self, key: int, name: Optional[str]):
        domain = self[key]
        self[key] = DomainView(domain.id, name, domain.color, domain.masked, domain.highlight)

    def set_color(self, key: int, color):
        domain = self[key]
        self[key] = DomainView(domain.id, domain.name, color, domain.masked, domain.highlight)

    def set_masked(self, key: int, masked: bool):
        domain = self[key]
        self[key] = DomainView(domain.id, domain.name, domain.color, masked, domain.highlight)

    def set_highlight(self, key: int, highlight: bool):
        domain = self[key]
        self[key] = DomainView(domain.id, domain.name, domain.color, domain.masked, highlight)


class DomainView:
    """Represents view settings for OpenMC cell or material.

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
    highlight : bool
        Indication of whether cell/material should be highlighted
        (defaults to False)
    """

    def __init__(self, id, name, color=None, masked=False, highlight=False):
        """ Initialize DomainView instance """

        self.id = id
        self.name = name
        self.color = color
        self.masked = masked
        self.highlight = highlight

    def __repr__(self):
        return ("id: {} \nname: {} \ncolor: {} \
                \nmask: {} \nhighlight: {}\n\n".format(self.id,
                                                         self.name,
                                                         self.color,
                                                         self.masked,
                                                         self.highlight))

    def __eq__(self, other):
        if isinstance(other, DomainView):
            return self.__dict__ == other.__dict__


class DomainTableModel(QAbstractTableModel):
    """ Abstract Table Model of cell/material view attributes """

    def __init__(self, domains: DomainViewDict):
        super().__init__()
        self.domains = domains
        self.keys = dict(enumerate(self.domains.defaults))

    def rowCount(self, index=QModelIndex()):
        return len(self.keys)

    def columnCount(self, index=QModelIndex()):
        return 6

    def data(self, index, role=Qt.DisplayRole):

        if not index.isValid() or not (0 <= index.row() < self.rowCount()):
            return None

        key = self.keys[index.row()]
        domain = self.domains[key]
        column = index.column()

        if role == Qt.DisplayRole:
            if column == ID:
                return domain.id
            elif column == NAME:
                return domain.name if domain.name is not None else '--'
            elif column == COLOR:
                return '' if domain.color is not None else '+'
            elif column == COLORLABEL:
                return (str(tuple(int(x) for x in domain.color))
                        if domain.color is not None else '--')
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

        elif role == Qt.BackgroundRole:
            color = domain.color
            if column == COLOR:
                if isinstance(color, str):
                    return QColor.fromRgb(*openmc.plots._SVG_COLORS[color])
                else:
                    return QColor.fromRgb(*color)

        elif role == Qt.CheckStateRole:
            if column == MASK:
                return Qt.Checked if domain.masked else Qt.Unchecked
            elif column == HIGHLIGHT:
                return Qt.Checked if domain.highlight else Qt.Unchecked

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):

        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return int(Qt.AlignLeft | Qt.AlignVCenter)
            return int(Qt.AlignRight | Qt.AlignVCenter)

        elif role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                headers = ['ID', 'Name', 'Color',
                           'SVG/RGB', 'Mask', 'Highlight']
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

        if not index.isValid() or not (0 <= index.row() < self.rowCount()):
            return False

        key = self.keys[index.row()]
        column = index.column()

        if column == NAME:
            self.domains.set_name(key, value if value else None)
        elif column == COLOR or column == COLORLABEL:
                # reset the color to the default value if the coloar value is None
                if value is None:
                    value = self.domains.get_default_color(key)
                self.domains.set_color(key, value)
        elif column == MASK:
            if role == Qt.CheckStateRole:
                self.domains.set_masked(key, Qt.CheckState(value) == Qt.Checked)
        elif column == HIGHLIGHT:
            if role == Qt.CheckStateRole:
                self.domains.set_highlight(key, Qt.CheckState(value) == Qt.Checked)

        self.dataChanged.emit(index, index)
        return True


class DomainDelegate(QItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def sizeHint(self, option, index):

        fm = option.fontMetrics
        column = index.column()

        if column == ID:
            return QSize(fm.boundingRect("XXXXXX").width(), fm.height())
        elif column == COLOR:
            return QSize(fm.boundingRect("XXXXXX").width(), fm.height())
        elif column == COLORLABEL:
            return QSize(fm.boundingRect("X(XXX, XXX, XXX)X").width(), fm.height())
        elif column == MASK:
            return QSize(fm.boundingRect("XXXX").width(), fm.height())
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
            color = index.data(Qt.BackgroundRole)
            color = 'white' if color is None else color
            editor.setCurrentColor(color)
        elif index.column() in (NAME, COLORLABEL):
            text = index.data(Qt.DisplayRole)
            if text != '--':
                editor.setText(text)

    def editorEvent(self, event, model, option, index):

        if index.column() in (COLOR, COLORLABEL):
            if (index.flags() & Qt.ItemFlag.ItemIsEditable) == Qt.ItemFlag.NoItemFlags:
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
            model.setData(index, None, Qt.BackgroundRole)
            model.setData(model.index(row, column+1), None, Qt.DisplayRole)
        elif column == COLOR:
            color = editor.currentColor()
            if color != QColor():
                color = color.getRgb()[:3]
                model.setData(index, color, Qt.BackgroundRole)
                model.setData(model.index(row, column+1),
                              color,
                              Qt.DisplayRole)
        elif column == COLORLABEL:
            if editor is None:
                model.setData(model.index(row, column-1),
                              None,
                              Qt.BackgroundRole)
                model.setData(index, None, Qt.DisplayRole)
            elif editor.text().lower() in openmc.plots._SVG_COLORS:
                svg = editor.text().lower()
                color = openmc.plots._SVG_COLORS[svg]
                model.setData(model.index(row, column-1),
                              color,
                              Qt.BackgroundRole)
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
                model.setData(model.index(row, column-1),
                              input,
                              Qt.BackgroundRole)
                model.setData(index, input, Qt.DisplayRole)
        else:
            QItemDelegate.setModelData(self, editor, model, index)
