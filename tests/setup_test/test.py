import filecmp
import pytest
from openmc_plotter.main_window import MainWindow, _openmcReload

@pytest.fixture
def run_in_tmpdir(tmpdir):
    orig = tmpdir.chdir()
    try:
        yield
    finally:
        orig.chdir()

def test_window(tmpdir, qtbot):
    orig = tmpdir.chdir()

    _openmcReload(model_path=str(orig))

    mw = MainWindow(model_path=orig)
    mw.loadGui()
    mw.saveImage(tmpdir / 'test.png')
    qtbot.addWidget(mw)

    filecmp.cmp(orig / 'ref.png', tmpdir / 'test.png')