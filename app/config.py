"""
Ρυθμίσεις και Διαδρομές Εφαρμογής (Application Configuration & Paths)
"""

import os
import sys
from pathlib import Path

# Εισαγωγή πληροφοριών έκδοσης από τη ρίζα
try:
    from version import __version__, __app_name__, GITHUB_REPO
except ImportError:
    __version__ = "1.0.6"
    __app_name__ = "Ηλεκτρονικό Πρωτόκολλο Εγγράφων"
    GITHUB_REPO = "grcomandos83-cyber/ELECTRONIC-DOCUMENT-PROTOCOL"

# Έλεγχος εκτέλεσης σε περιβάλλον PyInstaller (Frozen)
IS_FROZEN = getattr(sys, 'frozen', False)

# Ρίζα εγκατάστασης / πηγαίου κώδικα
if IS_FROZEN:
    APP_DIR = os.path.abspath(os.path.dirname(sys.executable))
else:
    # app/config.py -> app/ -> Protocols/ (root)
    APP_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def setup_environment():
    """
    Κλείδωμα Τρέχοντος Καταλόγου Εργασίας (Working Directory Lock).
    Αποτρέπει σφάλματα σχετικών διαδρομών όταν η εφαρμογή καλείται από
    εξωτερικές συντομεύσεις ή διεργασίες συστήματος.
    """
    if IS_FROZEN:
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(APP_DIR)


def get_base_data_dir() -> str:
    """
    Εντοπίζει τον βασικό κατάλογο αποθήκευσης δεδομένων (βάσης, συνημμένων, αντιγράφων).
    1. Portable / Development: Αν υπάρχει ήδη protocol.db στον τρέχοντα κατάλογο ή στο APP_DIR
    2. Installed mode: Χρήση του %APPDATA%\\Protokollo ώστε τα δεδομένα να μην αλλοιώνονται σε updates.
    """
    # 1. Portable mode: Έλεγχος τρέχοντος καταλόγου
    if os.path.exists("protocol.db"):
        return os.path.abspath(os.getcwd())

    # 1b. Dev mode ή portable στον κατάλογο της εφαρμογής
    if os.path.exists(os.path.join(APP_DIR, "protocol.db")) or not IS_FROZEN:
        return APP_DIR

    # 2. Installed mode: APPDATA
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    data_dir = os.path.join(appdata, "Protokollo")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


# Βασικές διαδρομές δεδομένων
BASE_DIR = get_base_data_dir()
DB_FILE = os.path.join(BASE_DIR, "protocol.db")
ATTACHMENTS_DIR = os.path.join(BASE_DIR, "attachments")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")


def get_app_icon_path() -> str:
    """Εντοπίζει το εικονίδιο της εφαρμογής είτε σε dev mode είτε σε PyInstaller package."""
    candidates = [
        os.path.join(APP_DIR, "assets", "app_icon.ico"),
        os.path.join(os.path.dirname(sys.executable), "assets", "app_icon.ico"),
        os.path.join(os.path.dirname(sys.executable), "_internal", "assets", "app_icon.ico"),
        os.path.join(os.getcwd(), "assets", "app_icon.ico"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


# Σταθερές Ελληνικού Ημερολογίου
GREEK_WEEKDAYS = [
    "Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"
]
GREEK_MONTHS = [
    "Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου",
    "Ιουλίου", "Αυγούστου", "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"
]

# Αναγνωριστικό εφαρμογής στα Windows για τη γραμμή εργασιών (Taskbar)
APP_USER_MODEL_ID = "cyber.protocol.desktop.1.0"
