from .notifications import SensitiveColumnNote, ZipVarianceNote, OutliersNote, PerformanceNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [SensitiveColumnNote, ZipVarianceNote],
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
