from types import SimpleNamespace

import numpy as np
import pytest
from PySide6 import QtGui, QtWidgets

from openmc_plotter.plotgui import PlotImage


class FakeClipboard:

    def __init__(self):
        self.image = None

    def setImage(self, image):
        self.image = image


@pytest.fixture
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_copy_image_to_clipboard_crops_to_plot_and_preserves_alpha(
    qapp, monkeypatch
):
    scroll = QtWidgets.QScrollArea()
    scroll.resize(220, 160)
    main_window = SimpleNamespace(
        logicalDpiX=lambda: 100,
        zoom=100,
        coord_label=SimpleNamespace(show=lambda: None, hide=lambda: None),
        statusBar=lambda: SimpleNamespace(showMessage=lambda *args, **kwargs: None),
    )
    plot = PlotImage(model=None, parent=scroll, main_window=main_window)
    scroll.setWidget(plot)
    plot.resize(400, 300)
    plot.figure.clear()
    plot.ax = plot.figure.subplots()
    plot.ax.imshow(np.zeros((10, 10, 4)))
    scroll.show()
    qapp.processEvents()
    scroll.horizontalScrollBar().setValue(40)
    scroll.verticalScrollBar().setValue(30)
    qapp.processEvents()

    fake_clipboard = FakeClipboard()
    monkeypatch.setattr(
        QtGui.QGuiApplication,
        "clipboard",
        staticmethod(lambda: fake_clipboard),
    )

    try:
        assert plot.copyImageToClipboard()
    finally:
        plot.close()
        scroll.close()

    assert fake_clipboard.image is not None
    assert not fake_clipboard.image.isNull()
    assert fake_clipboard.image.hasAlphaChannel()

    canvas_width, canvas_height = plot.get_width_height()
    expected_width = round(
        min(scroll.viewport().width(), plot.width()) * canvas_width / plot.width()
    )
    expected_height = round(
        min(scroll.viewport().height(), plot.height()) * canvas_height / plot.height()
    )
    assert fake_clipboard.image.width() == pytest.approx(expected_width, abs=1)
    assert fake_clipboard.image.height() == pytest.approx(expected_height, abs=1)
    assert fake_clipboard.image.width() < canvas_width
    assert fake_clipboard.image.height() < canvas_height

    center = fake_clipboard.image.pixelColor(
        fake_clipboard.image.width() // 2,
        fake_clipboard.image.height() // 2,
    )
    assert center.alpha() == 0
