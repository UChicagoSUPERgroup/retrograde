from .notifications import WelcomeNote, ProtectedColumnNote, MissingDataNote, ProxyColumnNote, ErrorSliceNote, ModelReportNote, UncertaintyNote
from .config import MODE

NOTES = [WelcomeNote, ProtectedColumnNote,
         MissingDataNote, ProxyColumnNote,
         ModelReportNote, UncertaintyNote]

if MODE == "NO_EXP":
    CONTEXT = [
        (".*", ".*", ".*"),
        (".*", ".*", ".*"),
        (".*", ".*", ".*"),
        (".*", ".*", ".*"),
        (".*", ".*", ".*"),
        (".*", ".*", ".*"),
    ]
if MODE == "EXP_CTS":
    CONTEXT = [
        (".*", ".*", ".*"),
        (".*", ".*", ".*"),
        ("clean", ".*", ".*"),
        ("feature_select", ".*", ".*"),
        ("model", ".*", ".*"),
        ("model", ".*", ".*"),
    ]
if MODE == "EXP_END":
    CONTEXT = [
        (".*", ".*", "model_select"),
        (".*", ".*", "model_select"),
        ("clean", ".*", "model_select"),
        ("feature_select", ".*", "model_select"),
        ("model", ".*", "model_select"),
        ("model", ".*", "model_select"),
    ]
if MODE == "EXP_NONE":
    CONTEXT = [
        ("NULL", "NULL"),
        ("NULL", "NULL"),
        ("NULL", "NULL"),
        ("NULL", "NULL"),
        ("NULL", "NULL"),
        ("NULL", "NULL"),
    ]
SLICE_K = 2 # number of error slices to show users for each FPR/FNR
