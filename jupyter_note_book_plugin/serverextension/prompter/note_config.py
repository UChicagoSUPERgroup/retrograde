from .notifications import WelcomeNote, ProtectedColumnNote, MissingDataNote, ProxyColumnNote, ErrorSliceNote, ModelReportNote, UncertaintyNote
from .config import MODE

NOTES = [WelcomeNote, ProtectedColumnNote,
         MissingDataNote, ProxyColumnNote,
         ModelReportNote, UncertaintyNote]

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
        (".*", ".*", "end"),
        (".*", ".*", "end"),
        ("clean", ".*", "end"),
        ("feature_select", ".*", "end"),
        ("model", ".*", "end"),
        ("model", ".*", "end"),
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
