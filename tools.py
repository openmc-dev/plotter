from PySide2 import QtCore, QtGui, QtWidgets
from scientific_spin_box import ScientificDoubleSpinBox
from common_widgets import HorizontalLine

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
        self.yResBox = QtWidgets.QSpinBox()
        self.zResBox = QtWidgets.QSpinBox()

        self.layout.addWidget(QtWidgets.QLabel("X steps:"), 4, 0)
        self.layout.addWidget(self.xResBox, 4, 1)
        self.layout.addWidget(QtWidgets.QLabel("Y steps:"), 4, 2)
        self.layout.addWidget(self.yResBox, 4, 3)
        self.layout.addWidget(QtWidgets.QLabel("Z steps:"), 4, 4)
        self.layout.addWidget(self.zResBox, 4, 5)

        self.exportButton = QtWidgets.QPushButton("Export")

        self.layout.addWidget(self.exportButton, 5, 0)
