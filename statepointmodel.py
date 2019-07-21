
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
        return [ (tally.id, tally.name, tally) for tally in self._sp.tallies ]

    def open(self):
        if self.is_open:
            return
        self._sp = openmc.statepoint.StatePoint(self.filename)
        self.is_open = True

    def close(self):
        self._sp = None
        self.is_open = False
