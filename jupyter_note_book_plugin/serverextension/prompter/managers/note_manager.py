import re

class NoteManager:
    """
    Manage which notes are shown and whether to update 
    or create notes
    """    
    def __init__(self, db, log, notes, context):

        self.notes = [note(db) for note in notes]
        self.context = context

        # context is a list of tuples with regex expressions of same
        # length as context. Each tuple is of size 3, and has a 
        # start expr, continue expr, and show expr.

        # the start expr is when to start looking for the expr
        # the continue expr defines when to keep looking for more/updating
        # the note, and the show expr controls display

        self.db = db
        self.log = log

        # Notifications need 1. a is_displayed flag 2. a expunge method

    def update_notes(self, cell_id, kernel_id, env, dfs, non_dfs, cell_type):  
        """
        update notes on basis of cell type
        """
        for note,context in zip(self.notes, self.context):
            if (note.displayed and re.match(context[1], cell_type)) or \
               (re.match(context[0], cell_type)):
                self.log.debug(f"[NoteManager] checking {note}, displayed {note.displayed}, {cell_type}, {context}")
                if note.feasible(cell_id, env,dfs, non_dfs):
                    note.make_response(env, kernel_id, cell_id)
                    note.started=True
                note.update(env, kernel_id, cell_id, dfs, non_dfs)

    def make_responses(self, cell_id, kernel_id, exec_ct, cell_type, dfs, non_dfs):

        resp = {}
        resp["kernel_id"] = kernel_id

        for note, context in zip(self.notes, self.context):
            if note.started and re.match(context[2], cell_type):
                note.expunge(dfs, non_dfs)
                for note_data in note.data.values():
                    for note_entry in note_data:
                        if note_entry["type"] not in resp:
                            resp[note_entry["type"]] = []
                        resp[note_entry["type"]].append(note_entry)
                        self.db.store_response(kernel_id, cell_id, exec_ct, note_entry)
                note.displayed = True
            else:
                note.displayed = False
        return resp 
class KernelNoteManager:
   
    """
    Handle routing of note manager requests by kernel_id
    """
 
    def __init__(self, db, log, notes, context):

        self.log = log
        self._managers = {}
        self._init_args = (db, log, notes, context)

    def update_notes(self, cell_id, kernel_id, env, dfs, non_dfs, cell_mode):
        """
        update notes associated with kernel_id, create note manager context if 
        no one exists for that specific context
        """
        if kernel_id not in self._managers:
            self.log.info(f"[KernelNoteManager] making new note manager for {kernel_id}")
            self._managers[kernel_id] = NoteManager(*self._init_args)
        self._managers[kernel_id].update_notes(cell_id, kernel_id, env, dfs, non_dfs, cell_mode)

    def make_responses(self, kernel_id, cell_id, exec_ct, cell_mode, dfs, non_dfs):
        """make responses for note manager associated with kernel_id"""
        return self._managers[kernel_id].make_responses(cell_id, kernel_id, exec_ct, cell_mode, dfs, non_dfs)
