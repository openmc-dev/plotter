from PySide2 import QtCore, QtGui, QtWidgets
import numpy as np
import copy
from scientific_spin_box import ScientificDoubleSpinBox
from custom_widgets import HorizontalLine
from time import sleep
import openmc

try:
    import vtk
    _HAVE_VTK = True
except ImportError:
    _HAVE_VTK = False

class ExportTallyDataDialog(QtWidgets.QDialog):

    def __init__(self, model, FM, parent=None):
        super().__init__(parent)

        self.model = model
        self.FM = FM
        self.parent = parent

        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

        # disable interaction with main window while this is open
        self.setModal(True)

    def show(self):
        cv = self.model.currentView

        if not self.model.statepoint:
            msg = QtWidgets.QMessageBox()
            msg.setText("No statepoint file loaded.")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return

        if not cv.selectedTally:
            msg = QtWidgets.QMessageBox()
            msg.setText("No tally selected.")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return

        self.populate()

        super().show()

    def closeEvent(self, event):
        super().closeEvent(event)

    @staticmethod
    def _warn(msg):
        msg_box = QMessageBox()
        msg_box.setText(msg)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    def populate(self):
        cv = self.model.currentView
        tally = self.model.statepoint.tallies[cv.selectedTally]

        self.xminBox = ScientificDoubleSpinBox()
        self.xmaxBox = ScientificDoubleSpinBox()
        self.yminBox = ScientificDoubleSpinBox()
        self.ymaxBox = ScientificDoubleSpinBox()
        self.zminBox = ScientificDoubleSpinBox()
        self.zmaxBox = ScientificDoubleSpinBox()

        self.layout.addWidget(QtWidgets.QLabel("X-min:"), 0, 0)
        self.layout.addWidget(self.xminBox, 0, 1)
        self.layout.addWidget(QtWidgets.QLabel("X-max:"), 0, 2)
        self.layout.addWidget(self.xmaxBox, 0, 3)

        self.layout.addWidget(QtWidgets.QLabel("Y-min:"), 1, 0)
        self.layout.addWidget(self.yminBox, 1, 1)
        self.layout.addWidget(QtWidgets.QLabel("Y-max:"), 1, 2)
        self.layout.addWidget(self.ymaxBox, 1, 3)

        self.layout.addWidget(QtWidgets.QLabel("Z-min:"), 2, 0)
        self.layout.addWidget(self.zminBox, 2, 1)
        self.layout.addWidget(QtWidgets.QLabel("z-max:"), 2, 2)
        self.layout.addWidget(self.zmaxBox, 2, 3)

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

        self.layout.addWidget(QtWidgets.QLabel("X steps:"), 4, 0)
        self.layout.addWidget(self.xResBox, 4, 1)
        self.layout.addWidget(QtWidgets.QLabel("Y steps:"), 4, 2)
        self.layout.addWidget(self.yResBox, 4, 3)
        self.layout.addWidget(QtWidgets.QLabel("Z steps:"), 4, 4)
        self.layout.addWidget(self.zResBox, 4, 5)

        self.dataLabelField = QtWidgets.QLineEdit()
        self.dataLabelField.setText("Tally {}".format(cv.selectedTally))
        self.layout.addWidget(QtWidgets.QLabel("Data Label:"), 5, 0)
        self.layout.addWidget(self.dataLabelField, 5, 1)

        self.exportButton = QtWidgets.QPushButton("Export")
        self.exportButton.clicked.connect(self.export_data)
        self.exportButton.setEnabled(_HAVE_VTK)

        self.layout.addWidget(self.exportButton, 6, 0)

        if tally.contains_filter(openmc.MeshFilter):

            mesh_filter = tally.find_filter(openmc.MeshFilter)
            mesh = mesh_filter.mesh
            assert(mesh.n_dimension == 3)

            llc = mesh.lower_left
            self.xminBox.setValue(llc[0])
            self.yminBox.setValue(llc[1])
            self.zminBox.setValue(llc[2])

            urc = mesh.upper_right
            self.xmaxBox.setValue(urc[0])
            self.ymaxBox.setValue(urc[1])
            self.zmaxBox.setValue(urc[2])

            dims = mesh.dimension
            self.xResBox.setValue(dims[0])
            self.yResBox.setValue(dims[1])
            self.zResBox.setValue(dims[2])

            self.xminBox.setEnabled(False)
            self.xminBox.setToolTip("Using MeshFilter to set bounds automatically.")
            self.xmaxBox.setEnabled(False)
            self.xmaxBox.setToolTip("Using MeshFilter to set bounds automatically.")
            self.yminBox.setEnabled(False)
            self.yminBox.setToolTip("Using MeshFilter to set bounds automatically.")
            self.ymaxBox.setEnabled(False)
            self.ymaxBox.setToolTip("Using MeshFilter to set bounds automatically.")
            self.zminBox.setEnabled(False)
            self.zminBox.setToolTip("Using MeshFilter to set bounds automatically.")
            self.zmaxBox.setEnabled(False)
            self.zmaxBox.setToolTip("Using MeshFilter to set bounds automatically.")


            self.xResBox.setEnabled(False)
            self.xResBox.setToolTip("Using MeshFilter to set resolution automatically.")
            self.yResBox.setEnabled(False)
            self.yResBox.setToolTip("Using MeshFilter to set resolution automatically.")
            self.zResBox.setEnabled(False)
            self.zResBox.setToolTip("Using MeshFilter to set resolution automatically.")

    def export_data(self):

        # collect necessary information from the export box
        llc = np.array((self.xminBox.value(), self.yminBox.value(), self.zminBox.value()))
        urc = np.array((self.xmaxBox.value(), self.ymaxBox.value(), self.zmaxBox.value()))
        res = np.array((self.xResBox.value(), self.yResBox.value(), self.zResBox.value()))
        dx, dy, dz = (urc - llc) / res

        if any(llc >= urc):
            _warn("Bounds of export data are invalid.")
            return

        if any(res <= 0):
            _warn("Resolution of the export mesh is invalid. Values must be" \
                  " <= 0.")
            return

        filename, ext = QtWidgets.QFileDialog.getSaveFileName(self,
                                                              "Set VTK Filename",
                                                              "untitled",
                                                              "VTK Image (.vti)")


        print("Exporting data with resolution: {}".format(res))
        # create empty array to store our values
        data = np.zeros(res[::-1], dtype=float)

        # get a copy of the current view
        cv = self.model.currentView
        av = self.model.activeView
        view = copy.deepcopy(cv)

        # get a view of the tally data for each x,y slice:

        x0, y0, z0 = (llc + urc) / 2.0
        view.width = urc[0] - llc[0]
        view.height = urc[1] - llc[1]
        view.h_res = res[0]
        view.v_res = res[1]

        z0 = llc[2] + dz / 2.0

        progressBar = QtWidgets.QProgressDialog("Accumulating data...",
                                                "Abort Copy",
                                                0,
                                                res[2])
        progressBar.setWindowModality(QtCore.Qt.WindowModal)

        for k in range(res[2]):
            z = z0 + k * dz
            view.origin = (x0, y0, z)
            view.basis = 'xy'
            self.model.activeView = view
            self.model.makePlot()
            image_data = self.model.create_tally_image(view)
            data[k, :,:] = image_data[0]
            progressBar.setValue(k)
            if progressBar.wasCanceled():
                # restore the previous active
                self.model.currentView = cv
                self.model.activeView = av
                self.model.makePlot()
                return

        vtk_image = vtk.vtkImageData()
        vtk_image.SetDimensions(res + 1)
        vtk_image.SetSpacing(dx, dy, dz)
        vtk_image.SetOrigin(llc)
        vtk_data = vtk.vtkDoubleArray()
        label = self.dataLabelField.text()
        vtk_data.SetName(self.dataLabelField.text())
        vtk_data.SetArray(data, data.size, True)
        vtk_image.GetCellData().AddArray(vtk_data)

        progressBar.setLabel(QtWidgets.QLabel("Writing VTK Image file: {}...".format(filename)))

        writer = vtk.vtkXMLImageDataWriter()
        writer.SetInputData(vtk_image)
        writer.SetFileName(filename)
        writer.Write()

        progressBar.setLabel(QtWidgets.QLabel("Export complete"))
        progressBar.setValue(res[2])

        # restore the previous active
        self.model.currentView = cv
        self.model.activeView = av
        self.model.makePlot()
