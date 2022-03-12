from .notifications import WelcomeNote, ProtectedColumnNote, MissingDataNote, ProxyColumnNote, ErrorSliceNote, ModelReportNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "all" : [WelcomeNote, ProtectedColumnNote], # should trigger always
        "intro" :[ProxyColumnNote, ProtectedColumnNote],
        "tutorial" : [ProxyColumnNote, ProtectedColumnNote],
        "null_clean" : [MissingDataNote, ProtectedColumnNote],
        "model" : [ModelReportNote],
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
