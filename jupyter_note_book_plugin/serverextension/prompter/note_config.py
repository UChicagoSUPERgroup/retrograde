from .notifications import ProtectedColumnNote, ZipVarianceNote, OutliersNote, PerformanceNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [ProtectedColumnNote, OutliersNote],
        "null_clean" : [],
        "model" : [ZipVarianceNote, PerformanceNote],
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
