from .notifications import ProtectedColumnNote, MissingDataNote, ProxyColumnNote, ErrorSliceNote, EqualizedOddsNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [ProxyColumnNote],
        "null_clean" : [ProtectedColumnNote],
        "model" : [ErrorSliceNote, EqualizedOddsNote],
        "end" : []
    }
if MODE == "EXP_END":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [],
        "null_clean" : [],
        "model" : [],
        "end" : [ProtectedColumnNote, ProxyColumnNote, OutliersNote, EqualizedOddsNote]
    }

SLICE_K = 2 # number of error slices to show users for each FPR/FNR
