from .notifications import MissingDataNote, ProtectedColumnNote, OutliersNote, EqualizedOddsNote, ProxyColumnNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [ProxyColumnNote],
        "null_clean" : [ProtectedColumnNote, ProxyColumnNote, MissingDataNote],
        "model" : [EqualizedOddsNote],
        "end" : []
    }
if MODE == "EXP_END":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [],
        "null_clean" : [],
        "model" : [],
        "end" : [ProtectedColumnNote, ProxyColumnNote, MissingDataNote, OutliersNote, EqualizedOddsNote]
    }
