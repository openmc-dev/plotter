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

def test_copy_image_to_clipboard(tmpdir, monkeypatch, qtbot):
    orig = tmpdir.chdir()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    mw = MainWindow(model_path=orig)
    _openmcReload(model_path=orig)
    mw.loadGui()
    qtbot.addWidget(mw)
    mw.show()

    class FakeClipboard:
        def __init__(self):
            self.image = None

        def setImage(self, image):
            self.image = image

    fake_clipboard = FakeClipboard()
    monkeypatch.setattr(QtGui.QGuiApplication,
                        'clipboard',
                        staticmethod(lambda: fake_clipboard))

    try:
        assert mw.waitForPlotIdle(60000)
        mw.model.currentView.domainVisible = False
        mw.plotIm.updatePixmap()
        assert mw.copyImageToClipboard()
    finally:
        orig.chdir()

    assert fake_clipboard.image is not None
    assert not fake_clipboard.image.isNull()
    assert fake_clipboard.image.hasAlphaChannel()

    canvas_width, canvas_height = mw.plotIm.get_width_height()
    expected_width = round(
        min(mw.frame.viewport().width(), mw.plotIm.width())
        * canvas_width
        / mw.plotIm.width()
    )
    expected_height = round(
        min(mw.frame.viewport().height(), mw.plotIm.height())
        * canvas_height
        / mw.plotIm.height()
    )
    assert fake_clipboard.image.width() == pytest.approx(expected_width, abs=1)
    assert fake_clipboard.image.height() == pytest.approx(expected_height, abs=1)

    center = fake_clipboard.image.pixelColor(fake_clipboard.image.width() // 2,
                                             fake_clipboard.image.height() // 2)
    assert center.alpha() == 0

    mw.close()
