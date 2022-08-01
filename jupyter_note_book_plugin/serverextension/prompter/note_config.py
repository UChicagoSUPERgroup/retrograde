from .notifications import WelcomeNote, ProtectedColumnNote, MissingDataNote, ProxyColumnNote, ErrorSliceNote, ModelReportNote, UncertaintyNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "all" : [WelcomeNote, ProtectedColumnNote], # should trigger always
        "intro" : [],
        "clean" : [MissingDataNote],
        "feature_select" : [ProxyColumnNote],
        "model" : [ModelReportNote, UncertaintyNote],
        "end" : []  
    }
    SHOW = ["all", "intro", "clean", "feature_select", "model", "end"]
if MODE == "EXP_END":
    NOTE_RULES = {
        "all" : [WelcomeNote, ProtectedColumnNote],
        "intro" :[],
        "clean" : [MissingDataNote],
        "feature_select" : [ProxyColumnNote],
        "model" : [ModelReportNote, UncertaintyNote],
        "end" : []
    }
    SHOW = ["end"]
if MODE == "EXP_NONE":
    NOTE_RULES = {
        "all" : [],
        "intro" : [],
        "clean" : [],
        "feature_select" : [],
        "model" : [],
        "end" : []
    }
    SHOW = []
SLICE_K = 2 # number of error slices to show users for each FPR/FNR
