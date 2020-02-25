"""
This module contains means for prioritizing which cells need to be 
documented
"""

import pandas as pd

class Heuristics:
    
    """
    Tests a set of rules using the database handled by the
    handler object. The handler argument should be of type DbHandler
    """

    def __init__(self, dbhandler, analysis_environment):

        self._db = dbhandler
        self._env = analysis_environment

        self.data_watch = DatasetRules()

    def process_cell(self, cell_code, notebook):
        
        self._db.add_entry(cell_code)
        self._env.cell_exec(cell_code)

        
class DatasetRules:
    """
    has dataset been added, changed or removed?
    """
    def __init__(self):
        self.previous_datasets = set()

    def env_query(self, env):

        entry_points = [(v["source"], v["format"]) for v env.entry_points.values()]
        entry_points = set(entry_points)

        if len(entry_points^self.previous_datasets) != 0:   

            self.trigger = True

            if len(entry_points - self.previous_datasets) != 0 and \
                len(self.previous_datasets - entry_points) != 0:

                self.value = ("update", entry_points^self.previous_datasets)
                self.previous_datasets = entry_points

            elif len(entry_points - self.previous_datasets) != 0:
                self.value = ("add", entry_points - self.previous_datasets)
                self.previous_datasets = entry_points

            else:
                self.value = ("remove", self.previous_datasets - entry_points)
                self.previous_datasets = entry_points
        else:
            self.trigger = False
