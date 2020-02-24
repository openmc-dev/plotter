import decorator

import openmc.lib

from openmc_plotter.main_window import MainWindow, _openmcReload

# decorator for loading and unloading the local model

def test_window(qtbot):
    _openmcReload()

    mw = MainWindow()
    mw.loadGui()
    mw.plotIm.figure.savefig("test.png")
    qtbot.addWidget(mw)
