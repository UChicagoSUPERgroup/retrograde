from .notifications import WelcomeNote, ProtectedColumnNote, MissingDataNote, ProxyColumnNote, ErrorSliceNote, ModelReportNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "all" : [WelcomeNote, ProtectedColumnNote], # should trigger always
        "intro" : [],
        "tutorial" : [],
        "null_clean" : [MissingDataNote],
        "model" : [ProxyColumnNote, ModelReportNote],
        "end" : []
    }
if MODE == "EXP_END":
    NOTE_RULES = {
        "all" : [],
        "intro" :[],
        "tutorial" : [],
        "null_clean" : [],
        "model" : [ProtectedColumnNote, MissingDataNote, ProxyColumnNote, ModelReportNote],
        "end" : []
    }
if MODE == "EXP_NONE":
    NOTE_RULES = {
        "all" : [],
        "intro" : [],
        "tutorial" : [],
        "null_clean" : [],
        "model" : [],
        "end" : []
    }
SLICE_K = 2 # number of error slices to show users for each FPR/FNR
