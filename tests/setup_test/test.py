import filecmp
import shutil

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
    mw = MainWindow(model_path=orig)
    _openmcReload(model_path=orig)
    mw.loadGui()

    try:
        mw.saveImage(tmpdir / 'test.png')

        qtbot.addWidget(mw)
    finally:
        orig.chdir()

    filecmp.cmp(orig / 'ref.png', tmpdir / 'test.png')

    mw.close()

def test_batch_image(tmpdir, qtbot):
    orig = tmpdir.chdir()

    # move view file into tmpdir
    shutil.copy2(orig / 'test.pltvw', tmpdir)
    shutil.copy2(orig / 'test1.pltvw', tmpdir)

    _openmcReload(model_path=orig)

    mw = MainWindow(model_path=orig)
    mw.loadGui()

    try:
        mw.saveBatchImage('test.pltvw')
        qtbot.addWidget(mw)

        mw.saveBatchImage('test1.pltvw')
        qtbot.addWidget(mw)
    finally:
        orig.chdir()

    filecmp.cmp(orig / 'ref.png', tmpdir / 'test.png')
    filecmp.cmp(orig / 'ref1.png', tmpdir / 'test1.png')

    mw.close()