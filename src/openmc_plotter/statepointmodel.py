
import openmc


class StatePointModel():
    """
    Class for management of an openmc.StatePoint instance
    in the plotting application
    """
    def __init__(self, filename, open_file=False):
        self.filename = filename
        self._sp = None
        self.is_open = False

        if open_file:
            self.open()

    @property
    def tallies(self):
        return self._sp.tallies if self.is_open else {}

    @property
    def filters(self):
        return self._sp.filters if self.is_open else {}

    @property
    def universes(self):
        if self.is_open and self._sp.summary is not None:
            return self._sp.summary.geometry.get_all_universes()
        else:
            return {}

    def open(self):
        if self.is_open:
            return
        self._sp = openmc.StatePoint(self.filename)
        self.is_open = True

    def close(self):
        self._sp = None
        self.is_open = False
