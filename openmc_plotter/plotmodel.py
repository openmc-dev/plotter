from ast import literal_eval
from collections import defaultdict
import copy
import itertools
import threading

from PySide2.QtWidgets import QItemDelegate, QColorDialog, QLineEdit, QMessageBox
from PySide2.QtCore import QAbstractTableModel, QModelIndex, Qt, QSize, QEvent
from PySide2.QtGui import QColor
import openmc
import openmc.lib
import numpy as np

from .statepointmodel import StatePointModel
from .plot_colors import random_rgb, reset_seed

ID, NAME, COLOR, COLORLABEL, MASK, HIGHLIGHT = tuple(range(0, 6))

__VERSION__ = "0.2.1"

_VOID_REGION = -1
_NOT_FOUND = -2
_OVERLAP = -3

_MODEL_PROPERTIES = ('temperature', 'density')
_PROPERTY_INDICES = {'temperature': 0, 'density': 1}

_REACTION_UNITS = 'Reactions per Source Particle'
_FLUX_UNITS = 'Particle-cm per Source Particle'
_PRODUCTION_UNITS = 'Particles Produced per Source Particle'
_ENERGY_UNITS = 'eV per Source Particle'

_SPATIAL_FILTERS = (openmc.UniverseFilter,
                    openmc.MaterialFilter,
                    openmc.CellFilter,
                    openmc.MeshFilter)

_PRODUCTIONS = ('delayed-nu-fission', 'prompt-nu-fission', 'nu-fission',
               'nu-scatter', 'H1-production', 'H2-production',
               'H3-production', 'He3-production', 'He4-production')

_SCORE_UNITS = {p: _PRODUCTION_UNITS for p in _PRODUCTIONS}
_SCORE_UNITS['flux'] = 'Particle-cm/Particle'
_SCORE_UNITS['current'] = 'Particles per source Particle'
_SCORE_UNITS['events'] = 'Events per Source Particle'
_SCORE_UNITS['inverse-velocity'] = 'Particle-seconds per Source Particle'
_SCORE_UNITS['heating'] = _ENERGY_UNITS
_SCORE_UNITS['heating-local'] = _ENERGY_UNITS
_SCORE_UNITS['kappa-fission'] = _ENERGY_UNITS
_SCORE_UNITS['fission-q-prompt'] = _ENERGY_UNITS
_SCORE_UNITS['fission-q-recoverable'] = _ENERGY_UNITS
_SCORE_UNITS['decay-rate'] = 'Seconds^-1'
_SCORE_UNITS['damage-energy'] = _ENERGY_UNITS

_TALLY_VALUES = {'Mean': 'mean',
                 'Std. Dev.': 'std_dev',
                 'Rel. Error': 'rel_err'}

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
        ids : NumPy int array (v_res, h_res, 1)
            Mapping of plot coordinates to cell/material ID by pixel
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

        # Retrieve OpenMC Cells/Materials
        self.modelCells = openmc.lib.cells
        self.modelMaterials = openmc.lib.materials
        self.max_universe_levels = openmc.lib._coord_levels()

        # Cell/Material ID by coordinates
        self.ids = None
        self.instances = None

        self.version = __VERSION__

        # default statepoint value
        self._statepoint = None
        # default tally/filter info
        self.appliedFilters = ()
        self.appliedScores = ()
        self.appliedNuclides = ()

        # reset random number seed for consistent
        # coloring when reloading a model
        reset_seed()

        self.previousViews = []
        self.subsequentViews = []
        self.defaultView = self.getDefaultView()
        self.currentView = copy.deepcopy(self.defaultView)
        self.activeView = copy.deepcopy(self.defaultView)

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

        default = PlotView([xcenter, ycenter, zcenter], width, height)
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

        cv = self.currentView = copy.deepcopy(self.activeView)
        ids = openmc.lib.id_map(cv)
        props = openmc.lib.property_map(cv)

        self.cell_ids = ids[:, :, 0]
        self.instances = ids[:, :, 1]
        self.mat_ids = ids[:, :, 2]

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
                cell.color = random_rgb()

        for mat_id, mat in cv.materials.items():
            if mat.color is None:
                mat.color = random_rgb()

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
        # set model properties
        self.properties = props
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

    def storeCurrent(self):
        """ Add current view to previousViews list """
        self.previousViews.append(copy.deepcopy(self.currentView))

    def create_tally_image(self, view=None):
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
            msg_box.exec_()
            return (None, None, None, None, None)

        units_out = list(units)[0]

        if tally.contains_filter(openmc.MeshFilter):
            if tally_value == 'rel_err':
                # get both the std. dev. data and mean data
                # to create the relative error data
                mean_data = self._create_tally_mesh_image(tally,
                                                          'mean',
                                                          scores,
                                                          nuclides,
                                                          view)
                std_dev_data = self._create_tally_mesh_image(tally,
                                                             'std_dev',
                                                             scores,
                                                             nuclides,
                                                             view)
                image_data = 100 * np.divide(std_dev_data[0],
                                             mean_data[0],
                                             out=np.zeros_like(mean_data[0]),
                                             where=mean_data != 0)
                extents = mean_data[1]
                data_min = np.min(image_data)
                data_max = np.max(image_data)
                return image_data, extents, data_min, data_max, '% error'

            else:
                image = self._create_tally_mesh_image(tally,
                                                      tally_value,
                                                      scores,
                                                      nuclides,
                                                      view)
                return image + (units_out,)
        else:
            # same as above, get the std. dev. data
            # and mean date to produce the relative error data
            if tally_value == 'rel_err':
                mean_data = self._create_tally_domain_image(tally,
                                                            'mean',
                                                            scores,
                                                            nuclides,
                                                            view)
                std_dev_data = self._create_tally_domain_image(tally,
                                                           'std_dev',
                                                           scores,
                                                           nuclides,
                                                           view)
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
                                                        nuclides,
                                                        view)
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
                data[:, ...] = 0.0
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

    def _create_tally_mesh_image(self, tally, tally_value, scores, nuclides, view=None):
        # some variables used throughout
        if view is None:
            cv = self.currentView

        sp = self.statepoint
        mesh_filter = tally.find_filter(openmc.MeshFilter)
        mesh = mesh_filter.mesh

        def _do_op(array, tally_value, ax=0):
            if tally_value == 'mean':
                return np.sum(array, axis=ax)
            elif tally_value == 'std_dev':
                return np.sqrt(np.sum(array**2, axis=ax))

        # start with reshaped data
        data = tally.get_reshaped_data(tally_value)

        # determine basis indices
        if view.basis == 'xy':
            h_ind = 0
            v_ind = 1
            ax = 2
        elif view.basis == 'yz':
            h_ind = 1
            v_ind = 2
            ax = 0
        else:
            h_ind = 0
            v_ind = 2
            ax = 1

        # adjust corners of the mesh for a translation
        # applied to the mesh filter
        lower_left = mesh.lower_left
        upper_right = mesh.upper_right
        width = mesh.width
        dimension = mesh.dimension
        if hasattr(mesh_filter, 'translation') and mesh_filter.translation is not None:
            lower_left += mesh_filter.translation
            upper_right += mesh_filter.translation

        # For 2D meshes, add an extra z dimension
        if len(mesh.dimension) == 2:
            lower_left = np.hstack((lower_left, -1e50))
            upper_right = np.hstack((upper_right, 1e50))
            width = np.hstack((width, 2e50))
            dimension = np.hstack((dimension, 1))

        # reduce data to the visible slice of the mesh values
        k = int((view.origin[ax] - lower_left[ax]) // width[ax])

        # setup slice
        data_slice = [None, None, None]
        data_slice[h_ind] = slice(dimension[h_ind])
        data_slice[v_ind] = slice(dimension[v_ind])
        data_slice[ax] = k

        if k < 0 or k > dimension[ax]:
            return (None, None, None, None)

        # move mesh axes to the end of the filters
        filter_idx = [type(filter) for filter in tally.filters].index(openmc.MeshFilter)
        data = np.moveaxis(data, filter_idx, -1)

        # reshape data (with zyx ordering for mesh data)
        data = data.reshape(data.shape[:-1] + tuple(dimension[::-1]))
        data = data[..., data_slice[2], data_slice[1], data_slice[0]]

        # sum over the rest of the tally filters
        for tally_filter in tally.filters:
            if type(tally_filter) == openmc.MeshFilter:
                continue

            if tally_filter in self.appliedFilters:
                selected_bins = self.appliedFilters[tally_filter]
                # sum filter data for the selected bins
                data = data[np.array(selected_bins)].sum(axis=0)
            else:
                # if the filter is completely unselected,
                # set all of it's data to zero and remove the axis
                data[:, ...] = 0.0
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

        # get dataset's min/max
        data_min = np.min(data)
        data_max = np.max(data)

        # set image data, reverse y-axis
        image_data = data[::-1, ...]

        # return data extents (in cm) for the tally
        extents = [lower_left[h_ind], upper_right[h_ind],
                   lower_left[v_ind], upper_right[v_ind]]

        return image_data, extents, data_min, data_max


class PlotView(openmc.lib.plot._PlotBase):
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
    h_res : int
        Horizontal resolution of plot image
    v_res : int
        Vertical resolution of plot image
    aspectLock : bool
        Indication of whether aspect lock should be maintained to
        prevent image stretching/warping
    basis : {'xy', 'xz', 'yz'}
        The basis directions for the plot
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
    color_overlaps : bool
        Indicator of whether or not overlaps will be shown
    overlap_color : 3-tuple of int
        RGB color to apply for cell overlap regions
    cells : Dict of DomainView instances
        Dictionary of cell view settings by ID
    materials : Dict of DomainView instances
        Dictionary of material view settings by ID
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
    selectedTally : str
        Label of the currently selected tally
    """

    def __init__(self, origin, width, height):
        """ Initialize PlotView attributes """

        super().__init__()

        # View Parameters
        self.level = -1
        self.origin = origin
        self.width = width
        self.height = height
        self.h_res = 1000
        self.v_res = 1000
        self.aspectLock = True
        self.basis = 'xy'

        # Geometry Plot
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
        # Get model domain info
        self.cells = self.getDomains('cell')
        self.materials = self.getDomains('material')

        # Tally Viz Settings
        self.tallyDataColormap = 'spectral'
        self.tallyDataVisible = True
        self.tallyDataAlpha = 1.0
        self.tallyDataIndicator = False
        self.tallyDataUserMinMax = False
        self.tallyDataMin = 0.0
        self.tallyDataMax = np.inf
        self.tallyDataLogScale = False
        self.tallyMaskZeroValues = False
        self.clipTallyData = False
        self.tallyValue = "Mean"
        self.tallyContours = False
        self.tallyContourLevels = ""
        self.selectedTally = None

    def __hash__(self):
        return hash(self.__dict__.__str__() + self.__str__())

    @staticmethod
    def getDomains(domain_type):
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

        lib_domain = None
        if domain_type == 'cell':
            lib_domain = openmc.lib.cells
        elif domain_type == 'material':
            lib_domain = openmc.lib.materials

        domains = {}
        for domain, domain_obj in lib_domain.items():
            name = domain_obj.name
            domains[domain] = DomainView(domain, name, random_rgb())

        # always add void to a material domain at the end
        if domain_type == 'material':
            void_id = _VOID_REGION
            domains[void_id] = DomainView(void_id, "VOID",
                                          (255, 255, 255),
                                          False,
                                          False)

        return domains

    def getDataLimits(self):
        return self.data_minmax

    def getColorLimits(self, property):
        if self.use_custom_minmax[property]:
            return self.user_minmax[property]
        else:
            return self.data_minmax[property]

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
        self.h_res = self.h_res
        self.v_res = self.v_res
        self.basis = view.basis

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

    def __init__(self, domains):
        super().__init__()
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
            color = domain.color
            if column == COLOR:
                if isinstance(color, tuple):
                        return QColor.fromRgb(*color)
                elif isinstance(color, str):
                    return QColor.fromRgb(*openmc.plots._SVG_COLORS[color])

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
                domain.highlight = True if value == Qt.Checked else False

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
                model.setData(model.index(row, column+1),
                              color,
                              Qt.DisplayRole)
        elif column == COLORLABEL:
            if editor is None:
                model.setData(model.index(row, column-1),
                              None,
                              Qt.BackgroundColorRole)
                model.setData(index, None, Qt.DisplayRole)
            elif editor.text().lower() in openmc.plots._SVG_COLORS:
                svg = editor.text().lower()
                color = openmc.plots._SVG_COLORS[svg]
                model.setData(model.index(row, column-1),
                              color,
                              Qt.BackgroundColorRole)
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
                              Qt.BackgroundColorRole)
                model.setData(index, input, Qt.DisplayRole)
        else:
            QItemDelegate.setModelData(self, editor, model, index)
