from .notifications import ProtectedColumnNote, MissingDataNote, ProxyColumnNote, ErrorSliceNote, ModelReportNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [ProxyColumnNote],
        "null_clean" : [ProtectedColumnNote],
        "model" : [ModelReportNote, ErrorSliceNote],
        "end" : []
    }
if MODE == "EXP_END":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [],
        "null_clean" : [],
        "model" : [],
        "end" : [ProtectedColumnNote, ProxyColumnNote, OutliersNote, ModelReportNote]
    }

SLICE_K = 2 # number of error slices to show users for each FPR/FNR
