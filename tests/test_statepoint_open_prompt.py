from types import SimpleNamespace

from openmc_plotter import main_window


class FakeButton:
    def __init__(self):
        self.text = None

    def setText(self, text):
        self.text = text


class FakeMessageBox:
    Yes = 1
    Cancel = 2
    Ok = 4
    Information = 8
    Warning = 16
    next_result = Cancel
    instances = []

    def __init__(self, *args, **kwargs):
        self.text = None
        self.icon = None
        self.standard_buttons = None
        self.default_button = None
        self.buttons = {}
        type(self).instances.append(self)

    def setText(self, text):
        self.text = text

    def setIcon(self, icon):
        self.icon = icon

    def setStandardButtons(self, buttons):
        self.standard_buttons = buttons

    def setDefaultButton(self, button):
        self.default_button = button

    def button(self, button):
        return self.buttons.setdefault(button, FakeButton())

    def exec(self):
        return type(self).next_result


def make_window(events):
    status_bar = SimpleNamespace(
        showMessage=lambda message, timeout=None: events.append(
            ("status", message, timeout)
        )
    )
    statepoint = SimpleNamespace(
        filename="current.h5",
        close=lambda: events.append("close-current-statepoint"),
    )
    model = SimpleNamespace(
        statepoint=statepoint,
        currentView=SimpleNamespace(selectedTally=17),
        activeView=SimpleNamespace(selectedTally=17),
    )

    def open_statepoint(filename):
        events.append(("open-statepoint", filename))
        model.statepoint = SimpleNamespace(
            filename=filename,
            close=lambda: events.append(("close-statepoint", filename)),
        )

    model.openStatePoint = open_statepoint

    window = SimpleNamespace(
        model=model,
        statusBar=lambda: status_bar,
        updateDataMenu=lambda: events.append("update-data-menu"),
        tallyPanel=SimpleNamespace(
            selectTally=lambda: events.append("select-tally"),
            update=lambda: events.append("update-tally-panel"),
        ),
        plotIm=SimpleNamespace(updatePixmap=lambda: events.append("update-pixmap")),
    )
    window.closeStatePoint = lambda: main_window.MainWindow.closeStatePoint(window)
    return window


def test_open_statepoint_cancel_keeps_current_file(monkeypatch):
    events = []
    FakeMessageBox.instances = []
    FakeMessageBox.next_result = FakeMessageBox.Cancel
    window = make_window(events)

    def fake_get_open_file_name(*args, **kwargs):
        events.append("show-open-dialog")
        return ("replacement.h5", "*.h5")

    monkeypatch.setattr(main_window, "QMessageBox", FakeMessageBox)
    monkeypatch.setattr(
        main_window.QFileDialog, "getOpenFileName", fake_get_open_file_name
    )

    main_window.MainWindow.openStatePoint(window)

    assert events == []
    assert window.model.statepoint.filename == "current.h5"
    assert len(FakeMessageBox.instances) == 1
    assert FakeMessageBox.instances[0].text == (
        "A statepoint file is currently open. Continue to close it and open "
        "a new one?"
    )
    assert FakeMessageBox.instances[0].button(FakeMessageBox.Yes).text == "Continue"


def test_open_statepoint_continue_closes_current_file_before_reopening(
    monkeypatch,
):
    events = []
    FakeMessageBox.instances = []
    FakeMessageBox.next_result = FakeMessageBox.Yes
    window = make_window(events)

    def fake_get_open_file_name(*args, **kwargs):
        events.append("show-open-dialog")
        return ("replacement.h5", "*.h5")

    monkeypatch.setattr(main_window, "QMessageBox", FakeMessageBox)
    monkeypatch.setattr(
        main_window.QFileDialog, "getOpenFileName", fake_get_open_file_name
    )

    main_window.MainWindow.openStatePoint(window)

    assert events.index("close-current-statepoint") < events.index("show-open-dialog")
    assert ("open-statepoint", "replacement.h5") in events
    assert ("status", "Opened statepoint file: replacement.h5", 5000) in events
    assert window.model.currentView.selectedTally is None
    assert window.model.activeView.selectedTally is None
    assert window.model.statepoint.filename == "replacement.h5"
