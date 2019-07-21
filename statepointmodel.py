
import openmc
import os

class StatePointModel():

    def __init__(self, filename, open_file=False):
        self.filename = filename
        self._sp = None

        self.is_open = open_file
        if self.is_open:
            self.open()

    def tally_list(self):
        if self._sp is None:
            return []
        else:
            return [ (id, tally.name, tally) for id, tally in self._sp.tallies.items() ]

    def open(self):
        if self.is_open:
            return
        self._sp = openmc.statepoint.StatePoint(self.filename)
        self.is_open = True

    def close(self):
        self._sp = None
        self.is_open = False
