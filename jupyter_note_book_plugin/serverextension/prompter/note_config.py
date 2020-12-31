from .notifications import SensitiveColumnNote
from .config import MODE

if MODE == "EXP_CTS":
    NOTE_RULES = {
        "intro" :[],
        "tutorial" : [SensitiveColumnNote],
        "null_clean" : [],
        "model" : [SensitiveColumnNote],
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
