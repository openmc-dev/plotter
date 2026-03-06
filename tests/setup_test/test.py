import filecmp
import shutil

import pytest
from PySide6 import QtGui, QtWidgets

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
        assert mw.waitForPlotIdle(60000)
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

def test_copy_image_to_clipboard(tmpdir, monkeypatch):
    orig = tmpdir.chdir()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    mw = MainWindow(model_path=orig)
    _openmcReload(model_path=orig)
    mw.loadGui()

    class FakeClipboard:
        def __init__(self):
            self.pixmap = None

        def setPixmap(self, pixmap):
            self.pixmap = pixmap

    fake_clipboard = FakeClipboard()
    monkeypatch.setattr(QtGui.QGuiApplication,
                        'clipboard',
                        staticmethod(lambda: fake_clipboard))

    try:
        assert mw.waitForPlotIdle(60000)
        assert mw.copyImageToClipboard()
    finally:
        orig.chdir()

    assert fake_clipboard.pixmap is not None
    assert not fake_clipboard.pixmap.isNull()

    mw.close()
