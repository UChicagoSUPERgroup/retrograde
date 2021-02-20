from .notifications import ProtectedColumnNote, ZipVarianceNote, OutliersNote, PerformanceNote, EqualizedOddsNote, ProxyColumnNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [ProxyColumnNote],
        "null_clean" : [],
        "model" : [ZipVarianceNote, EqualizedOddsNote],
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
