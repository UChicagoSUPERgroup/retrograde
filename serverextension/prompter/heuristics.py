"""
This module contains means for prioritizing which cells need to be 
documented
"""

class RuleTester(object):
    
    """
    Tests a set of rules using the database handled by the
    handler object. The handler argument should be of type DbHandler
    """

    def __init__(self, handler):
        self._handler = handler
      
    def add_rule(self, rule):
        """Add a rule to be tested. the rule should be a function that returns a boolean value"""
        # TODO
        pass

    def test(self):
        """For each cell in the database, return how many rules are true"""
        # TODO
        pass 
