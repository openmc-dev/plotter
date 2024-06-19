import copy

import numpy as np
import openmc
from PySide6 import QtCore, QtWidgets

from .custom_widgets import HorizontalLine
from .scientific_spin_box import ScientificDoubleSpinBox


class SourceSitesDialog(QtWidgets.QDialog):
    def __init__(self, model, font_metric, parent=None):
        super().__init__(parent)

        self.setWindowTitle('Sample Source Sites')
        self.model = model
        self.font_metric = font_metric
        self.parent = parent

        self.layout = QtWidgets.QFormLayout()
        self.setLayout(self.layout)

        self.populate()

    def populate(self):
        self.nSitesBox = QtWidgets.QSpinBox(self)
        self.nSitesBox.setMaximum(1_000_000)
        self.nSitesBox.setMinimum(0)
        self.nSitesBox.setValue(1000)
        self.nSitesBox.setToolTip('Number of source sites to sample from the OpenMC source')

        self.sites_visible = QtWidgets.QCheckBox(self)
        self.sites_visible.setChecked(self.model.sourceSitesVisible)
        self.sites_visible.setToolTip('Toggle visibility of source sites on the slice plane')
        self.sites_visible.stateChanged.connect(self._toggle_source_sites)

        self.colorButton = QtWidgets.QPushButton(self)
        self.colorButton.setToolTip('Select color for displaying source sites on the slice plane')
        self.colorButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.colorButton.setFixedHeight(self.font_metric.height() * 1.5)
        self.colorButton.clicked.connect(self._select_source_site_color)
        rgb = self.model.sourceSitesColor
        self.colorButton.setStyleSheet(
            f"border-radius: 8px; background-color: rgb{rgb}")

        self.toleranceBox = ScientificDoubleSpinBox()
        self.toleranceBox.setToolTip('Slice axis tolerance for displaying source sites on the slice plane')
        self.toleranceBox.setValue(self.model.sourceSitesTolerance)
        self.toleranceBox.valueChanged.connect(self._set_source_site_tolerance)
        self.toleranceBox.setEnabled(self.model.sourceSitesApplyTolerance)

        self.toleranceToggle = QtWidgets.QCheckBox(self)
        self.toleranceToggle.setChecked(self.model.sourceSitesApplyTolerance)
        self.toleranceToggle.stateChanged.connect(self._toggle_tolerance)

        self.sampleButton = QtWidgets.QPushButton("Sample New Sites")
        self.sampleButton.setToolTip('Sample new source sites from the OpenMC source')
        self.sampleButton.clicked.connect(self._sample_sites)

        self.closeButton = QtWidgets.QPushButton("Close")
        self.closeButton.clicked.connect(self.close)

        self.layout.addRow("Source Sites:", self.nSitesBox)
        self.layout.addRow("Visible:", self.sites_visible)
        self.layout.addRow("Color:", self.colorButton)
        self.layout.addRow('Tolerance:', self.toleranceBox)
        self.layout.addRow('Apply tolerance:', self.toleranceToggle)
        self.layout.addRow(HorizontalLine())
        self.layout.addRow(self.sampleButton)
        self.layout.addRow(self.closeButton)

    def _sample_sites(self):
        self.model.getExternalSourceSites(self.nSitesBox.value())
        self.parent.applyChanges()

    def _toggle_source_sites(self):
        self.model.sourceSitesVisible = self.sites_visible.isChecked()
        self.parent.applyChanges()

    def _select_source_site_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            rgb = self.model.sourceSitesColor = color.getRgb()[:3]
            self.colorButton.setStyleSheet(
                f"border-radius: 8px; background-color: rgb{rgb}")
            self.parent.applyChanges()

    def _toggle_tolerance(self):
        self.model.sourceSitesApplyTolerance = self.toleranceToggle.isChecked()
        self.toleranceBox.setEnabled(self.toleranceToggle.isChecked())
        self.parent.applyChanges()

    def _set_source_site_tolerance(self):
        self.model.sourceSitesTolerance = self.toleranceBox.value()
        self.parent.applyChanges()


class ExportDataDialog(QtWidgets.QDialog):
    """
    A dialog to facilitate generation of VTK files for
    the current model and tally data.
    """
    def __init__(self, model, font_metric, parent=None):
        super().__init__(parent)

        self.model = model
        self.font_metric = font_metric
        self.parent = parent

        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

        # disable interaction with main window while this is open
        self.setModal(True)

    def show(self):
        self.populate()
        super().show()

    @staticmethod
    def _warn(msg):
        msg_box = QtWidgets.QMessageBox()
        msg_box.setText(msg)
        msg_box.setIcon(QtWidgets.QMessageBox.Information)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg_box.exec()

    def populate(self):
        cv = self.model.currentView

        self.xminBox = ScientificDoubleSpinBox()
        self.xmaxBox = ScientificDoubleSpinBox()
        self.yminBox = ScientificDoubleSpinBox()
        self.ymaxBox = ScientificDoubleSpinBox()
        self.zminBox = ScientificDoubleSpinBox()
        self.zmaxBox = ScientificDoubleSpinBox()

        self.bounds_spin_boxes = (self.xminBox, self.xmaxBox,
                                  self.yminBox, self.ymaxBox,
                                  self.zminBox, self.zmaxBox)

        row = 0

        self.layout.addWidget(QtWidgets.QLabel("X-min:"), row, 0)
        self.layout.addWidget(self.xminBox, row, 1)
        self.layout.addWidget(QtWidgets.QLabel("X-max:"), row, 2)
        self.layout.addWidget(self.xmaxBox, row, 3)

        row += 1

        self.layout.addWidget(QtWidgets.QLabel("Y-min:"), row, 0)
        self.layout.addWidget(self.yminBox, row, 1)
        self.layout.addWidget(QtWidgets.QLabel("Y-max:"), row, 2)
        self.layout.addWidget(self.ymaxBox, row, 3)

        row += 1

        self.layout.addWidget(QtWidgets.QLabel("Z-min:"), row, 0)
        self.layout.addWidget(self.zminBox, row, 1)
        self.layout.addWidget(QtWidgets.QLabel("Z-max:"), row, 2)
        self.layout.addWidget(self.zmaxBox, row, 3)

        row +=1
        self.layout.addWidget(HorizontalLine(), 3, 0, 1, 6)

        self.xResBox = QtWidgets.QSpinBox()
        self.xResBox.setMaximum(1E6)
        self.xResBox.setMinimum(0)
        self.yResBox = QtWidgets.QSpinBox()
        self.yResBox.setMaximum(1E6)
        self.yResBox.setMinimum(0)
        self.zResBox = QtWidgets.QSpinBox()
        self.zResBox.setMaximum(1E6)
        self.zResBox.setMinimum(0)

        row += 1

        self.layout.addWidget(QtWidgets.QLabel("X steps:"), row, 0)
        self.layout.addWidget(self.xResBox, row, 1)
        self.layout.addWidget(QtWidgets.QLabel("Y steps:"), row, 2)
        self.layout.addWidget(self.yResBox, row, 3)
        self.layout.addWidget(QtWidgets.QLabel("Z steps:"), row, 4)
        self.layout.addWidget(self.zResBox, row, 5)

        row += 1

        self.layout.addWidget(HorizontalLine(), row, 0, 1, 6)

        row += 1

        self.tallyCheckBox = QtWidgets.QCheckBox()
        self.layout.addWidget(QtWidgets.QLabel("Include tally data:"),
                              row, 0, 1, 2)
        self.layout.addWidget(self.tallyCheckBox, row, 2)

        row += 1

        self.dataLabelField = QtWidgets.QLineEdit()
        self.layout.addWidget(QtWidgets.QLabel("VTK Data Label:"), row, 0)
        self.layout.addWidget(self.dataLabelField, row, 1, 1, 2)
        if cv.selectedTally:
            self.dataLabelField.setText("Tally {}".format(cv.selectedTally))
        else:
            self.dataLabelField.setText("No tally selected")
            self.dataLabelField.setEnabled(False)
            self.tallyCheckBox.setEnabled(False)

        row += 1

        self.geomCheckBox = QtWidgets.QCheckBox()
        self.layout.addWidget(QtWidgets.QLabel("Include Cells:"),
                              row, 0, 1, 2)
        self.layout.addWidget(self.geomCheckBox, row, 2)

        row += 1

        self.matsCheckBox = QtWidgets.QCheckBox()
        self.layout.addWidget(QtWidgets.QLabel("Include Materials:"),
                              row, 0, 1, 2)
        self.layout.addWidget(self.matsCheckBox, row, 2)

        row += 1

        self.tempCheckBox = QtWidgets.QCheckBox()
        self.layout.addWidget(QtWidgets.QLabel("Include Temperature:"),
                              row, 0, 1, 2)
        self.layout.addWidget(self.tempCheckBox, row, 2)

        row += 1

        self.densityCheckBox = QtWidgets.QCheckBox()
        self.layout.addWidget(QtWidgets.QLabel("Include Density:"),
                              row, 0, 1, 2)
        self.layout.addWidget(self.densityCheckBox, row, 2)

        row += 1

        self.layout.addWidget(HorizontalLine(), row, 0, 1, 6)

        row += 1

        self.exportButton = QtWidgets.QPushButton("Export to VTK")
        self.exportButton.clicked.connect(self.export_data)

        self.layout.addWidget(self.exportButton, row, 5, 1, 2)

        if cv.selectedTally:
            tally = self.model.statepoint.tallies[cv.selectedTally]
        else:
            tally = None

        if tally and tally.contains_filter(openmc.MeshFilter):

            mesh_filter = tally.find_filter(openmc.MeshFilter)
            mesh = mesh_filter.mesh
            assert(mesh.n_dimension == 3)

            bbox = mesh.bounding_box

            llc = bbox.lower_left
            self.xminBox.setValue(llc[0])
            self.yminBox.setValue(llc[1])
            self.zminBox.setValue(llc[2])

            urc = bbox.upper_right
            self.xmaxBox.setValue(urc[0])
            self.ymaxBox.setValue(urc[1])
            self.zmaxBox.setValue(urc[2])

            bounds_msg = "Using MeshFilter to set bounds automatically."
            for box in self.bounds_spin_boxes:
                box.setEnabled(False)
                box.setToolTip(bounds_msg)

            dims = mesh.dimension
            if len(dims) == 3:
                self.xResBox.setValue(dims[0])
                self.yResBox.setValue(dims[1])
                self.zResBox.setValue(dims[2])

                resolution_msg = "Using MeshFilter to set resolution automatically."
                self.xResBox.setEnabled(False)
                self.xResBox.setToolTip(resolution_msg)
                self.yResBox.setEnabled(False)
                self.yResBox.setToolTip(resolution_msg)
                self.zResBox.setEnabled(False)
                self.zResBox.setToolTip(resolution_msg)

        else:
            # initialize using the bounds of the current view
            llc = cv.llc
            self.xminBox.setValue(llc[0])
            self.yminBox.setValue(llc[1])
            self.zminBox.setValue(llc[2])

            urc = cv.urc
            self.xmaxBox.setValue(urc[0])
            self.ymaxBox.setValue(urc[1])
            self.zmaxBox.setValue(urc[2])

            self.xResBox.setValue(10)
            self.yResBox.setValue(10)
            self.zResBox.setValue(10)

    def export_data(self):
        # cache current and active views
        av = self.model.activeView
        try:
            # export the tally data
            self._export_data()
        finally:
            # always reset to the original view
            self.model.activeView = av
            self.model.makePlot()

    def _export_data(self):

        import vtk

        # collect necessary information from the export box
        llc = np.array((self.xminBox.value(),
                        self.yminBox.value(),
                        self.zminBox.value()))
        urc = np.array((self.xmaxBox.value(),
                        self.ymaxBox.value(),
                        self.zmaxBox.value()))
        res = np.array((self.xResBox.value(),
                        self.yResBox.value(),
                        self.zResBox.value()))
        dx, dy, dz = (urc - llc) / res

        if any(llc >= urc):
            self._warn("Bounds of export data are invalid.")
            return

        filename, ext = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Set VTK Filename",
            "tally_data.vti",
            "VTK Image (.vti)")

        # check for cancellation
        if filename == "":
            return

        if filename[-4:] != ".vti":
            filename += ".vti"

        ### Generate VTK Data ###

        # create empty array to store our values
        export_tally_data = self.tallyCheckBox.checkState() == QtCore.Qt.Checked
        if export_tally_data:
            tally_data = np.zeros(res[::-1], dtype=float)

        # create empty arrays for other model properties if requested
        export_cells = self.geomCheckBox.checkState() == QtCore.Qt.Checked
        if export_cells:
            cells = np.zeros(res[::-1], dtype='int32')

        export_materials = self.matsCheckBox.checkState() == QtCore.Qt.Checked
        if export_materials:
            mats = np.zeros(res[::-1], dtype='int32')

        export_temperatures = self.tempCheckBox.checkState() == QtCore.Qt.Checked
        if export_temperatures:
            temps = np.zeros(res[::-1], dtype='float')

        export_densities = self.densityCheckBox.checkState() == QtCore.Qt.Checked
        if export_densities:
            rhos = np.zeros(res[::-1], dtype='float')

        # get a copy of the current view
        view = copy.deepcopy(self.model.currentView)

        # adjust view settings to match those set in the export dialog
        x0, y0, z0 = (llc + urc) / 2.0
        view.width = urc[0] - llc[0]
        view.height = urc[1] - llc[1]
        view.h_res = res[0]
        view.v_res = res[1]
        view.tallyDataVisible = True

        z0 = llc[2] + dz / 2.0

        # progress bar to make sure the user knows something is happening
        # large mesh tallies could take a long time to export
        progressBar = QtWidgets.QProgressDialog("Accumulating data...",
                                                "Cancel",
                                                0,
                                                res[2])
        progressBar.setWindowModality(QtCore.Qt.WindowModal)

        # get a view of the tally data for each x, y slice:
        for k in range(res[2]):
            z = z0 + k*dz
            view.origin = (x0, y0, z)
            view.basis = 'xy'
            self.model.activeView = view
            self.model.makePlot()

            if export_tally_data:
                image_data = self.model.create_tally_image(view)
                tally_data[k] = image_data[0][::-1]
            if export_cells:
                cells[k] = self.model.cell_ids[::-1]
            if export_materials:
                mats[k] = self.model.mat_ids[::-1]
            if export_temperatures:
                temps[k] = self.model.temperatures[::-1]
            if export_densities:
                rhos[k] = self.model.densities[::-1]

            progressBar.setValue(k)
            if progressBar.wasCanceled():
                return

        vtk_image = vtk.vtkImageData()
        vtk_image.SetDimensions(res + 1)
        vtk_image.SetSpacing(dx, dy, dz)
        vtk_image.SetOrigin(llc)

        if export_tally_data:
            # assign tally data to double array
            vtk_data = vtk.vtkDoubleArray()
            vtk_data.SetName(self.dataLabelField.text())
            vtk_data.SetArray(tally_data, tally_data.size, True)
            vtk_image.GetCellData().AddArray(vtk_data)

        if export_cells:
            cell_data = vtk.vtkIntArray()
            cell_data.SetName("cells")
            cell_data.SetArray(cells, cells.size, True)
            vtk_image.GetCellData().AddArray(cell_data)

        if export_materials:
            mat_data = vtk.vtkIntArray()
            mat_data.SetName("mats")
            mat_data.SetArray(mats, mats.size, True)
            vtk_image.GetCellData().AddArray(mat_data)

        if export_temperatures:
            temp_data = vtk.vtkDoubleArray()
            temp_data.SetName("temperature")
            temp_data.SetArray(temps, temps.size, True)
            vtk_image.GetCellData().AddArray(temp_data)

        if export_densities:
            rho_data = vtk.vtkDoubleArray()
            rho_data.SetName("density")
            rho_data.SetArray(rhos, rhos.size, True)
            vtk_image.GetCellData().AddArray(rho_data)

        progressBar.setLabel(
            QtWidgets.QLabel("Writing VTK Image file: {}...".format(filename)))

        writer = vtk.vtkXMLImageDataWriter()
        writer.SetInputData(vtk_image)
        writer.SetFileName(filename)
        writer.Write()

        progressBar.setLabel(QtWidgets.QLabel("Export complete"))
        progressBar.setValue(res[2])

        msg = QtWidgets.QMessageBox()
        msg.setText("Export complete!")
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec()
