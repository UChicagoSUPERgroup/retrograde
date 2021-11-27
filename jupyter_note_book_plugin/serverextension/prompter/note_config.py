from .notifications import ProtectedColumnNote, MissingDataNote, ProxyColumnNote, ErrorSliceNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [ProtectedColumnNote, ProxyColumnNote],
        "null_clean" : [ProxyColumnNote, MissingDataNote],
        "model" : [ErrorSliceNote],
        "end" : []
    }
if MODE == "EXP_END":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [],
        "null_clean" : [],
        "model" : [],
        "end" : [ProtectedColumnNote, ProxyColumnNote, MissingDataNote]
    }

SLICE_K = 2 # number of error slices to show users for each FPR/FNR
