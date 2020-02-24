
from openmc_plotter import MainWindow

def test_window(qtbot):

    mw = MainWindow()
    mw.show()
    qtbot.addWidget(mw)
