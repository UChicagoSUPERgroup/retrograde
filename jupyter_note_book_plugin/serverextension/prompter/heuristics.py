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

