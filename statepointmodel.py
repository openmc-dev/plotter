
import openmc
import os

class StatePointModel():

    def __init__(self, model, filename):

        self.filename = filename
        self._sp = openmc.statepoint.StatePoint(self.filename)
        self.model = model

    def tally_list(self):
        return [ (tally.id, tally.name, tally) for tally in self._sp.tallies ]
