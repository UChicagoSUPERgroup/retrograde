from .notifications import ProtectedColumnNote, OutliersNote, EqualizedOddsNote, ProxyColumnNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [OutliersNote],
        "null_clean" : [ProtectedColumnNote, ProxyColumnNote],
        "model" : [EqualizedOddsNote],
        "end" : []
    }
if MODE == "EXP_END":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [],
        "null_clean" : [],
        "model" : [],
        "end" : []
    }
