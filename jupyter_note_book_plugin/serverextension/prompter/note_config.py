from .notifications import SensitiveColumnNote, ZipVarianceNote, OutliersNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [OutliersNote],
        "null_clean" : [],
        "model" : [],
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
