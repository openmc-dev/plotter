
import openmc
import os

class StatePointModel():

    def __init__(self, filename, open_file=False):
        self.filename = filename
        self._sp = None
        self.is_open = False

        if open_file:
            self.open()

    @property
    def tallies(self):
        if self.is_open:
            return self._sp.tallies
        else:
            return {}

    def open(self):
        if self.is_open:
            return
        self._sp = openmc.statepoint.StatePoint(self.filename)
        self.is_open = True

    def close(self):
        self._sp = None
        self.is_open = False
