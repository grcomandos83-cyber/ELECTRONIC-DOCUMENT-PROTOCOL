import os
import sys

# ─────────────────────────────────────────────────────────────
# Κλείδωμα Τρέχοντος Καταλόγου Εργασίας (Working Directory Lock)
# Αποτρέπει σφάλματα διαδρομών όταν η εφαρμογή καλείται από
# εξωτερικές συντομεύσεις ή διεργασίες συστήματος.
# ─────────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

import shutil
import csv
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QMessageBox, QFileDialog, QInputDialog, QLabel
)
from PyQt6.QtCore import QTimer, QDate, Qt
from PyQt6.QtGui import QKeySequence, QShortcut, QAction, QIcon
import ctypes

def get_app_icon_path():
    """Εντοπίζει το εικονίδιο της εφαρμογής είτε σε dev mode είτε σε PyInstaller package."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app_icon.ico"),
        os.path.join(os.path.dirname(sys.executable), "assets", "app_icon.ico"),
        os.path.join(os.path.dirname(sys.executable), "_internal", "assets", "app_icon.ico"),
        os.path.join(os.getcwd(), "assets", "app_icon.ico"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""

from ui_protocol_form import Ui_MainWindow
from search_dialog import SearchDialog
import database
from version import __version__, __app_name__, GITHUB_REPO
from updater import AutoUpdater
from document_viewer import DocumentViewerDialog

GREEK_WEEKDAYS = [
    "Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"
]
GREEK_MONTHS = [
    "Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου",
    "Ιουλίου", "Αυγούστου", "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"
]


class ProtocolMainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        
        # Ensure all fields and labels are bold
        bold_font = self.font()
        bold_font.setBold(True)
        self.setFont(bold_font)
        for w in self.findChildren(QWidget):
            wf = w.font()
            wf.setBold(True)
            w.setFont(wf)

        # Set Window Title with Version
        self.setWindowTitle(f"{__app_name__} v{__version__}")

        # Set Window Icon
        icon_path = get_app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        # Permanent Version Indicator in Status Bar
        self.lbl_version_status = QLabel(f" Έκδοση: v{__version__} ", self)
        self.lbl_version_status.setStyleSheet("color: #1e395b; font-weight: bold; padding: 2px 8px;")
        self.statusbar.addPermanentWidget(self.lbl_version_status)

        # Ensure database is initialized
        database.init_db()

        self.current_records = []
        self.current_index = -1
        self.is_new_mode = False
        self.is_edit_mode = False
        self.is_dirty = False
        self.is_loading = False

        # Connect UI Signals
        self.init_signals()

        # Clock Timer
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()

        # Auto-Updater (αθόρυβος έλεγχος στο παρασκήνιο)
        self.auto_updater = AutoUpdater(parent=self)
        # Μικρή καθυστέρηση για να φορτώσει πρώτα η εφαρμογή
        QTimer.singleShot(3000, lambda: self.auto_updater.check_for_updates(silent=True))

        # Initial Load
        self.refresh_data()

    def on_field_changed(self):
        if not self.is_loading and (self.is_edit_mode or self.is_new_mode):
            self.set_protocol_button_state(True)

    def get_greek_datetime_str(self):
        now = datetime.now()
        wd = GREEK_WEEKDAYS[now.weekday()]
        m = GREEK_MONTHS[now.month - 1]
        return f"{wd}, {now.day} {m} {now.year} - {now.strftime('%H:%M:%S')}"

    def update_clock(self):
        self.lblClock.setText(self.get_greek_datetime_str())

    def init_signals(self):
        # Refresh shortcut (F5)
        self.shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        self.shortcut_refresh.activated.connect(self.refresh_data)

        # Top Buttons
        self.btnNewProtocol.clicked.connect(self.set_new_mode)
        self.btnEdit.clicked.connect(self.on_btn_edit_clicked)
        self.btnProtocol.clicked.connect(self.save_record)

        # Year filter
        self.comboSelectYear.currentTextChanged.connect(self.on_year_filter_change)

        # Incoming / Outgoing type change
        self.comboDocClass.currentTextChanged.connect(self.on_doc_class_changed)

        # Protocol search dropdown
        self.comboSearchProto.currentIndexChanged.connect(self.on_search_proto_selected)

        # Navigation Buttons
        self.btnNavFirst.clicked.connect(self.nav_first)
        self.btnNavPrev.clicked.connect(self.nav_prev)
        self.btnNavNext.clicked.connect(self.nav_next)
        self.btnNavLast.clicked.connect(self.nav_last)
        self.txtNavIndex.returnPressed.connect(self.on_nav_enter)

        # Photo Buttons
        self.btnInsertPhotoInc.clicked.connect(lambda: self.browse_photo(self.txtPhotoIncPath))
        self.btnOpenPhotoInc.clicked.connect(lambda: self.open_photo(self.txtPhotoIncPath.text()))
        self.btnInsertPhotoOut.clicked.connect(lambda: self.browse_photo(self.txtPhotoOutPath))
        self.btnOpenPhotoOut.clicked.connect(lambda: self.open_photo(self.txtPhotoOutPath.text()))

        # Search Controls
        self.txtSearchQuery.textChanged.connect(self.on_search_text_changed)
        self.btnClearFilter.clicked.connect(self.clear_filter)

        # Radio button changes re-trigger search
        self.rbOrigin.toggled.connect(lambda: self.on_search_text_changed(self.txtSearchQuery.text()))
        self.rbDest.toggled.connect(lambda: self.on_search_text_changed(self.txtSearchQuery.text()))
        self.rbOffice.toggled.connect(lambda: self.on_search_text_changed(self.txtSearchQuery.text()))
        self.rbDescInc.toggled.connect(lambda: self.on_search_text_changed(self.txtSearchQuery.text()))
        self.rbDescOut.toggled.connect(lambda: self.on_search_text_changed(self.txtSearchQuery.text()))

        # Menu Actions
        self.actionNewYear.triggered.connect(self.action_new_year)
        self.actionExit.triggered.connect(self.close)
        self.actionBackup.triggered.connect(self.action_backup)
        self.actionRestore.triggered.connect(self.action_restore)
        self.actionExport.triggered.connect(self.action_export)
        self.actionResetDB.triggered.connect(self.action_reset_db)
        self.actionAbout.triggered.connect(self.action_about)

        # Μενού: Έλεγχος Ενημερώσεων (δυναμική προσθήκη)
        menu_help = self.actionAbout.parent()
        if menu_help is not None:
            self.actionAppVersion = QAction(f"ℹ️ Έκδοση: v{__version__}", self)
            self.actionAppVersion.setEnabled(False)
            menu_help.addAction(self.actionAppVersion)

            self.actionCheckUpdates = QAction("🔄 Έλεγχος Ενημερώσεων...", self)
            menu_help.addAction(self.actionCheckUpdates)
            self.actionCheckUpdates.triggered.connect(self.action_check_updates)

        # Advanced Search Menu Actions
        self.actionIncDateProto.triggered.connect(lambda: self.open_advanced_search("ΕΙΣΕΡΧΟΜΕΝΑ", "protocol_date"))
        self.actionIncDateDoc.triggered.connect(lambda: self.open_advanced_search("ΕΙΣΕΡΧΟΜΕΝΑ", "doc_date"))
        self.actionOutDateProto.triggered.connect(lambda: self.open_advanced_search("ΕΞΕΡΧΟΜΕΝΑ", "protocol_date"))
        self.actionOutDateDoc.triggered.connect(lambda: self.open_advanced_search("ΕΞΕΡΧΟΜΕΝΑ", "doc_date"))

        # Field modifications change protocol button to Red
        self.txtDocType.textEdited.connect(self.on_field_changed)
        self.txtOrigin.textEdited.connect(self.on_field_changed)
        self.txtDestination.textEdited.connect(self.on_field_changed)
        self.txtOffice.textEdited.connect(self.on_field_changed)
        self.txtIncomingDesc.textChanged.connect(self.on_field_changed)
        self.txtOutgoingDesc.textChanged.connect(self.on_field_changed)
        self.txtRemarks.textChanged.connect(self.on_field_changed)
        self.chkCompleted.toggled.connect(self.on_field_changed)
        self.comboDocClass.currentIndexChanged.connect(self.on_field_changed)
        self.dateProtocol.dateChanged.connect(self.on_field_changed)
        self.dateIncoming.dateChanged.connect(self.on_field_changed)
        self.dateOutgoing.dateChanged.connect(self.on_field_changed)

    # ---------------- DATABASE & DATA HANDLING ----------------
    def refresh_data(self):
        if not self.check_unsaved_changes():
            return
        self.is_new_mode = False
        
        # Populate Year Combobox
        years = database.get_years()
        curr_year = datetime.now().year
        if curr_year not in years:
            years.insert(0, curr_year)
            
        self.comboSelectYear.blockSignals(True)
        self.comboSelectYear.clear()
        for y in sorted(years, reverse=True):
            self.comboSelectYear.addItem(str(y))
        
        # Default to current year
        curr_idx = self.comboSelectYear.findText(str(curr_year))
        if curr_idx >= 0:
            self.comboSelectYear.setCurrentIndex(curr_idx)
        else:
            self.comboSelectYear.setCurrentIndex(0)
        self.comboSelectYear.blockSignals(False)

        selected_year = int(self.comboSelectYear.currentText()) if self.comboSelectYear.currentText() else curr_year
        self.load_records_for_year(selected_year)

    def load_records_for_year(self, year, target_proto_num=None):
        records = database.get_all_records(year_filter=year)
        self.current_records = [dict(r) for r in records]
        
        # Update search proto dropdown
        self.comboSearchProto.blockSignals(True)
        self.comboSearchProto.clear()
        self.comboSearchProto.addItem("")
        for r in self.current_records:
            self.comboSearchProto.addItem(str(r["protocol_number"]))
        self.comboSearchProto.blockSignals(False)

        if self.current_records:
            # Default to latest protocol number (last item in records)
            idx_to_show = len(self.current_records) - 1
            if target_proto_num is not None:
                for i, r in enumerate(self.current_records):
                    if r.get("protocol_number") == target_proto_num:
                        idx_to_show = i
                        break
            self.current_index = idx_to_show
            self.display_record(self.current_records[self.current_index])
        else:
            self.current_index = -1
            self.clear_fields()
            self.txtCurrentYear.setText(str(year))
            self.txtProtocolNum.setText(str(database.get_next_protocol_number(year)))
            self.is_new_mode = True
            self.is_edit_mode = True
            self.set_form_read_only(False)
            self.update_buttons_ui()

        self.update_nav_labels()

    def display_record(self, record):
        if not record:
            return

        self.is_loading = True
        try:
            self.txtProtocolNum.setText(str(record.get("protocol_number", "")))
            self.txtCurrentYear.setText(str(record.get("year", "")))

            # Update search combo to reflect this protocol number
            self.comboSearchProto.blockSignals(True)
            proto_str = str(record.get("protocol_number", ""))
            p_idx = self.comboSearchProto.findText(proto_str)
            if p_idx >= 0:
                self.comboSearchProto.setCurrentIndex(p_idx)
            self.comboSearchProto.blockSignals(False)

            # Dates (format: YYYY-MM-DD in DB)
            def set_qdate(widget, date_str):
                if date_str:
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                        widget.setDate(QDate(dt.year, dt.month, dt.day))
                    except Exception:
                        pass

            set_qdate(self.dateProtocol, record.get("protocol_date"))
            set_qdate(self.dateIncoming, record.get("incoming_date"))
            set_qdate(self.dateOutgoing, record.get("outgoing_date"))

            # Doc class combo
            doc_class = record.get("doc_class") or ""
            if doc_class:
                idx = self.comboDocClass.findText(doc_class)
                self.comboDocClass.setCurrentIndex(idx if idx >= 0 else -1)
            else:
                self.comboDocClass.setCurrentIndex(-1)

            self.txtDocType.setText(record.get("doc_type") or "")
            self.txtOrigin.setText(record.get("incoming_origin") or "")
            self.txtIncomingDesc.setPlainText(record.get("incoming_desc") or "")
            self.txtPhotoIncPath.setText(record.get("incoming_file") or "")
            self.txtOffice.setText(record.get("processing_office") or "")
            self.chkCompleted.setChecked(bool(record.get("completed", 0)))
            self.txtRemarks.setPlainText(record.get("remarks") or "")

            # Outgoing
            self.txtDestination.setText(record.get("outgoing_dest") or "")
            self.txtOutgoingDesc.setPlainText(record.get("outgoing_desc") or "")
            self.txtPhotoOutPath.setText(record.get("outgoing_file") or "")
        finally:
            self.is_loading = False

        self.is_new_mode = False
        self.is_edit_mode = False
        self.is_dirty = False
        self.set_form_read_only(True)
        self.update_buttons_ui()

    def set_form_read_only(self, read_only: bool):
        # Text fields
        self.txtDocType.setReadOnly(read_only)
        self.txtOrigin.setReadOnly(read_only)
        self.txtIncomingDesc.setReadOnly(read_only)
        self.txtOffice.setReadOnly(read_only)
        self.txtRemarks.setReadOnly(read_only)
        self.txtPhotoIncPath.setReadOnly(read_only)

        self.txtDestination.setReadOnly(read_only)
        self.txtOutgoingDesc.setReadOnly(read_only)
        self.txtPhotoOutPath.setReadOnly(read_only)

        # Selectors & checks
        self.comboDocClass.setEnabled(not read_only)
        self.dateProtocol.setEnabled(not read_only)
        self.dateIncoming.setEnabled(not read_only)
        self.chkCompleted.setEnabled(not read_only)
        self.btnInsertPhotoInc.setEnabled(not read_only)

        if read_only:
            ro_style = "background-color: #f4f6f9; color: #111111; border: 1px solid #b0c4de; font-weight: bold;"
            self.txtDocType.setStyleSheet(ro_style)
            self.txtOrigin.setStyleSheet(ro_style)
            self.txtIncomingDesc.setStyleSheet(ro_style)
            self.txtOffice.setStyleSheet(ro_style)
            self.txtRemarks.setStyleSheet(ro_style)
            self.txtPhotoIncPath.setStyleSheet(ro_style)
            self.comboDocClass.setStyleSheet(ro_style)
            self.dateProtocol.setStyleSheet(ro_style)
            self.dateIncoming.setStyleSheet(ro_style)
        else:
            white_style = "background-color: white; color: black; border: 1px solid #7f9db9; font-weight: bold;"
            self.txtDocType.setStyleSheet(white_style)
            self.txtOrigin.setStyleSheet(white_style)
            self.txtIncomingDesc.setStyleSheet(white_style)
            self.txtOffice.setStyleSheet(white_style)
            self.txtRemarks.setStyleSheet(white_style)
            self.txtPhotoIncPath.setStyleSheet(white_style)
            self.comboDocClass.setStyleSheet(white_style)
            self.dateProtocol.setStyleSheet(white_style)
            self.dateIncoming.setStyleSheet(white_style)

        # Synchronize outgoing fields
        self.on_doc_class_changed(self.comboDocClass.currentText())

    def set_outgoing_enabled(self, enabled: bool):
        is_active_edit = (self.is_edit_mode or self.is_new_mode)
        self.dateOutgoing.setEnabled(enabled and is_active_edit)
        self.txtDestination.setEnabled(enabled)
        self.txtOutgoingDesc.setEnabled(enabled)
        self.btnInsertPhotoOut.setEnabled(enabled and is_active_edit)
        self.btnOpenPhotoOut.setEnabled(enabled)
        self.txtPhotoOutPath.setEnabled(enabled)

        if not enabled:
            disabled_style = "background-color: #dcdcdc; color: #777777; border: 1px solid #aaaaaa; font-weight: bold;"
            btn_disabled_style = "background-color: #d0d0d0; color: #888888; border: 1px solid #aaaaaa; border-radius: 2px; font-weight: bold;"
            self.dateOutgoing.setStyleSheet(disabled_style)
            self.txtDestination.setStyleSheet(disabled_style)
            self.txtOutgoingDesc.setStyleSheet(disabled_style)
            self.txtPhotoOutPath.setStyleSheet(disabled_style)
            self.btnInsertPhotoOut.setStyleSheet(btn_disabled_style)
            self.btnOpenPhotoOut.setStyleSheet(btn_disabled_style)
        else:
            if not is_active_edit:
                ro_style = "background-color: #f4f6f9; color: #111111; border: 1px solid #b0c4de; font-weight: bold;"
                self.dateOutgoing.setStyleSheet(ro_style)
                self.txtDestination.setStyleSheet(ro_style)
                self.txtOutgoingDesc.setStyleSheet(ro_style)
                self.txtPhotoOutPath.setStyleSheet(ro_style)
            else:
                white_style = "background-color: white; color: black; border: 1px solid #7f9db9; font-weight: bold;"
                self.dateOutgoing.setStyleSheet(white_style)
                self.txtDestination.setStyleSheet(white_style)
                self.txtOutgoingDesc.setStyleSheet(white_style)
                self.txtPhotoOutPath.setStyleSheet(white_style)

            btn_style = "background-color: white; border: 1px solid #7f9db9; border-radius: 2px; font-weight: bold;"
            self.btnInsertPhotoOut.setStyleSheet(btn_style)
            self.btnOpenPhotoOut.setStyleSheet(btn_style)

    def on_doc_class_changed(self, text):
        text = text.strip()
        if text == "ΕΙΣΕΡΧΟΜΕΝΟ":
            self.set_outgoing_enabled(False)
        elif text in ("ΕΞΕΡΧΟΜΕΝΟ", "ΜΕ ΑΠΑΝΤΗΣΗ"):
            self.set_outgoing_enabled(True)
        else:
            self.set_outgoing_enabled(False)

    def update_buttons_ui(self):
        if self.is_new_mode:
            # Creating new protocol
            self.btnEdit.setEnabled(True)
            self.btnEdit.setText("❌ Ακύρωση Νέου")
            self.btnEdit.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    font-weight: bold;
                    border: 1px solid #545b62;
                    border-radius: 2px;
                }
                QPushButton:hover { background-color: #5a6268; }
                QPushButton:pressed { background-color: #4e555b; }
            """)
            self.btnProtocol.setEnabled(True)
            self.btnProtocol.setText("Πρωτοκόληση")
            self.btnProtocol.setStyleSheet("""
                QPushButton {
                    background-color: #d80000;
                    color: white;
                    font-weight: bold;
                    font-size: 11pt;
                    border: 1px solid #a00000;
                    border-radius: 2px;
                }
                QPushButton:hover { background-color: #f01414; }
                QPushButton:pressed { background-color: #a00000; }
            """)
        elif self.is_edit_mode:
            # Editing existing protocol
            self.btnEdit.setEnabled(True)
            self.btnEdit.setText("❌ Ακύρωση")
            self.btnEdit.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    font-weight: bold;
                    border: 1px solid #545b62;
                    border-radius: 2px;
                }
                QPushButton:hover { background-color: #5a6268; }
                QPushButton:pressed { background-color: #4e555b; }
            """)
            self.btnProtocol.setEnabled(True)
            self.btnProtocol.setText("💾 Αποθήκευση Αλλαγών")
            self.btnProtocol.setStyleSheet("""
                QPushButton {
                    background-color: #d80000;
                    color: white;
                    font-weight: bold;
                    font-size: 10pt;
                    border: 1px solid #a00000;
                    border-radius: 2px;
                }
                QPushButton:hover { background-color: #f01414; }
                QPushButton:pressed { background-color: #a00000; }
            """)
        else:
            # View Mode (Read-Only)
            has_records = bool(self.current_records and self.current_index >= 0)
            self.btnEdit.setEnabled(has_records)
            self.btnEdit.setText("✏️ Επεξεργασία")
            if has_records:
                self.btnEdit.setStyleSheet("""
                    QPushButton {
                        background-color: #e67e22;
                        color: white;
                        font-weight: bold;
                        border: 1px solid #d35400;
                        border-radius: 2px;
                    }
                    QPushButton:hover { background-color: #f39c12; }
                    QPushButton:pressed { background-color: #d35400; }
                """)
            else:
                self.btnEdit.setStyleSheet("""
                    QPushButton {
                        background-color: #bdc3c7;
                        color: #7f8c8d;
                        font-weight: bold;
                        border: 1px solid #95a5a6;
                        border-radius: 2px;
                    }
                """)
            self.btnProtocol.setEnabled(False)
            self.btnProtocol.setText("Πρωτοκόληση")
            self.btnProtocol.setStyleSheet("""
                QPushButton:disabled {
                    background-color: #8faec9;
                    color: #eaf1f8;
                    font-weight: bold;
                    font-size: 11pt;
                    border: 1px solid #7a9cb9;
                    border-radius: 2px;
                }
            """)

    def on_btn_edit_clicked(self):
        if self.is_edit_mode or self.is_new_mode:
            # Cancel edit / new mode
            if self.is_dirty:
                reply = QMessageBox.question(
                    self,
                    "Ακύρωση Αλλαγών",
                    "Έχετε κάνει αλλαγές στην εγγραφή.\nΘέλετε να τις ακυρώσετε και να επανέλθουν τα αρχικά στοιχεία;",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            self.is_dirty = False
            self.is_new_mode = False
            self.is_edit_mode = False
            if 0 <= self.current_index < len(self.current_records):
                self.display_record(self.current_records[self.current_index])
            else:
                self.refresh_data()
        else:
            # Enter edit mode
            if not self.current_records or self.current_index < 0:
                return
            self.is_edit_mode = True
            self.set_form_read_only(False)
            self.update_buttons_ui()
            self.txtDocType.setFocus()

    def clear_fields(self):
        self.is_loading = True
        try:
            today = QDate.currentDate()
            self.dateProtocol.setDate(today)
            self.dateIncoming.setDate(today)
            self.dateOutgoing.setDate(today)

            self.comboDocClass.setCurrentIndex(-1)
            self.set_outgoing_enabled(False)

            self.txtDocType.clear()
            self.txtOrigin.clear()
            self.txtIncomingDesc.clear()
            self.txtPhotoIncPath.clear()
            self.txtOffice.clear()
            self.chkCompleted.setChecked(False)
            self.txtRemarks.clear()

            self.txtDestination.clear()
            self.txtOutgoingDesc.clear()
            self.txtPhotoOutPath.clear()
        finally:
            self.is_loading = False

    def set_new_mode(self):
        if not self.check_unsaved_changes():
            return
        self.is_new_mode = True
        self.is_edit_mode = True
        self.clear_fields()
        year_str = self.comboSelectYear.currentText()
        if year_str.isdigit():
            active_year = int(year_str)
        else:
            active_year = datetime.now().year
        self.txtCurrentYear.setText(str(active_year))
        next_num = database.get_next_protocol_number(active_year)
        self.txtProtocolNum.setText(str(next_num))
        self.lblNavOf.setText(f"από {len(self.current_records)}")
        self.txtNavIndex.setText("*")

        self.set_form_read_only(False)
        self.update_buttons_ui()
        self.comboDocClass.setFocus()

    def save_record(self):
        # Validation: check if doc_class is selected
        doc_class = self.comboDocClass.currentText().strip()
        if not doc_class or self.comboDocClass.currentIndex() == -1:
            QMessageBox.warning(self, "Προσοχή", "Επιλέξτε ΕΙΣΕΡΧΟΜΕΝΟ ή ΕΞΕΡΧΟΜΕΝΟ")
            self.comboDocClass.setFocus()
            return False

        # Validation: For ΕΙΣΕΡΧΟΜΕΝΟ, ΕΙΔΟΣ ΕΓΓΡΑΦΟΥ & ΥΠΗΡΕΣΙΑ ΠΟΥ ΠΡΟΕΡΧΕΤΑΙ are mandatory
        if doc_class == "ΕΙΣΕΡΧΟΜΕΝΟ":
            missing = []
            if not self.txtDocType.text().strip():
                missing.append("ΕΙΔΟΣ ΕΓΓΡΑΦΟΥ")
            if not self.txtOrigin.text().strip():
                missing.append("ΥΠΗΡΕΣΙΑ ΠΟΥ ΠΡΟΕΡΧΕΤΑΙ")
            if missing:
                QMessageBox.warning(
                    self, "Υποχρεωτικά Πεδία",
                    f"Για τα ΕΙΣΕΡΧΟΜΕΝΑ, τα παρακάτω πεδία είναι υποχρεωτικά:\n• " + "\n• ".join(missing)
                )
                if not self.txtDocType.text().strip():
                    self.txtDocType.setFocus()
                else:
                    self.txtOrigin.setFocus()
                return False

        try:
            year = int(self.txtCurrentYear.text())
        except ValueError:
            year = datetime.now().year

        try:
            proto_num = int(self.txtProtocolNum.text())
        except ValueError:
            proto_num = 0

        data = {
            "protocol_number": proto_num,
            "year": year,
            "protocol_date": self.dateProtocol.date().toString("yyyy-MM-dd"),
            "doc_class": doc_class,
            "incoming_date": self.dateIncoming.date().toString("yyyy-MM-dd"),
            "doc_type": self.txtDocType.text().strip(),
            "incoming_origin": self.txtOrigin.text().strip(),
            "incoming_desc": self.txtIncomingDesc.toPlainText().strip(),
            "incoming_file": self.txtPhotoIncPath.text().strip(),
            "processing_office": self.txtOffice.text().strip(),
            "completed": 1 if self.chkCompleted.isChecked() else 0,
            "remarks": self.txtRemarks.toPlainText().strip(),
            "outgoing_date": self.dateOutgoing.date().toString("yyyy-MM-dd"),
            "outgoing_dest": self.txtDestination.text().strip(),
            "outgoing_desc": self.txtOutgoingDesc.toPlainText().strip(),
            "outgoing_file": self.txtPhotoOutPath.text().strip()
        }

        if self.is_new_mode:
            _, assigned_num = database.insert_record(data)
            self.is_new_mode = False
            self.is_edit_mode = False
            self.is_dirty = False
            QMessageBox.information(self, "Επιτυχία", f"Το Πρωτόκολλο #{assigned_num}/{year} αποθηκεύτηκε επιτυχώς!")
            years = database.get_years()
            self.comboSelectYear.blockSignals(True)
            self.comboSelectYear.clear()
            for y in sorted(years, reverse=True):
                self.comboSelectYear.addItem(str(y))
            idx = self.comboSelectYear.findText(str(year))
            if idx >= 0:
                self.comboSelectYear.setCurrentIndex(idx)
            self.comboSelectYear.blockSignals(False)
            self.load_records_for_year(year, target_proto_num=assigned_num)
        else:
            if 0 <= self.current_index < len(self.current_records):
                # Proposal 2: Explicit Confirmation Dialog on Updating Existing Record
                reply = QMessageBox.question(
                    self,
                    "Επιβεβαίωση Τροποποίησης",
                    f"⚠️ ΠΡΟΣΟΧΗ:\nΠρόκειται να τροποποιήσετε το ήδη καταχωρημένο Πρωτόκολλο #{proto_num}/{year}.\n\n"
                    f"Είστε βέβαιοι ότι θέλετε να αποθηκευτούν οι αλλαγές;",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return False

                record_id = self.current_records[self.current_index]["id"]
                database.update_record(record_id, data)
                self.is_dirty = False
                self.is_edit_mode = False
                QMessageBox.information(self, "Επιτυχία", f"Το Πρωτόκολλο #{proto_num}/{year} ενημερώθηκε!")
                self.load_records_for_year(year, target_proto_num=proto_num)
            else:
                database.insert_record(data)
                self.is_dirty = False
                self.is_edit_mode = False
                self.refresh_data()
        return True

    # ---------------- NAVIGATION ----------------
    def update_nav_labels(self):
        total = len(self.current_records)
        curr = (self.current_index + 1) if (self.current_index >= 0 and total > 0) else 0
        self.txtNavIndex.setText(str(curr))
        self.lblNavOf.setText(f"από {total}")

    def nav_first(self):
        if not self.check_unsaved_changes():
            return
        if self.current_records:
            self.current_index = 0
            self.display_record(self.current_records[self.current_index])
            self.update_nav_labels()

    def nav_prev(self):
        if not self.check_unsaved_changes():
            return
        if self.current_records and self.current_index > 0:
            self.current_index -= 1
            self.display_record(self.current_records[self.current_index])
            self.update_nav_labels()

    def nav_next(self):
        if not self.check_unsaved_changes():
            return
        if self.current_records and self.current_index < len(self.current_records) - 1:
            self.current_index += 1
            self.display_record(self.current_records[self.current_index])
            self.update_nav_labels()

    def nav_last(self):
        if not self.check_unsaved_changes():
            return
        if self.current_records:
            self.current_index = len(self.current_records) - 1
            self.display_record(self.current_records[self.current_index])
            self.update_nav_labels()

    def on_nav_enter(self):
        try:
            idx = int(self.txtNavIndex.text()) - 1
            if 0 <= idx < len(self.current_records):
                if idx == self.current_index and not self.is_new_mode:
                    return
                if not self.check_unsaved_changes():
                    self.update_nav_labels()
                    return
                self.current_index = idx
                self.display_record(self.current_records[self.current_index])
                self.update_nav_labels()
        except ValueError:
            self.update_nav_labels()

    def on_year_filter_change(self, text):
        if not text.isdigit():
            return
        new_year = int(text)
        curr_year_str = self.txtCurrentYear.text().strip()
        if curr_year_str.isdigit() and int(curr_year_str) == new_year and not self.is_new_mode and not self.is_dirty:
            return

        if not self.check_unsaved_changes():
            self.comboSelectYear.blockSignals(True)
            idx = self.comboSelectYear.findText(curr_year_str)
            if idx >= 0:
                self.comboSelectYear.setCurrentIndex(idx)
            self.comboSelectYear.blockSignals(False)
            return

        self.load_records_for_year(new_year)

    def on_search_proto_selected(self, index):
        val = self.comboSearchProto.currentText()
        if not val or not val.isdigit():
            return
        num = int(val)
        if self.current_records and 0 <= self.current_index < len(self.current_records):
            if self.current_records[self.current_index].get("protocol_number") == num and not self.is_new_mode and not self.is_dirty:
                return

        if not self.check_unsaved_changes():
            self.comboSearchProto.blockSignals(True)
            if self.current_records and 0 <= self.current_index < len(self.current_records):
                curr_p = str(self.current_records[self.current_index].get("protocol_number", ""))
                idx = self.comboSearchProto.findText(curr_p)
                if idx >= 0:
                    self.comboSearchProto.setCurrentIndex(idx)
            self.comboSearchProto.blockSignals(False)
            return

        for i, r in enumerate(self.current_records):
            if r["protocol_number"] == num:
                self.current_index = i
                self.display_record(r)
                self.update_nav_labels()
                break

    # ---------------- SEARCH & FILTER ----------------
    def on_search_text_changed(self, text):
        if self.is_dirty:
            if not self.check_unsaved_changes():
                self.txtSearchQuery.blockSignals(True)
                self.txtSearchQuery.clear()
                self.txtSearchQuery.blockSignals(False)
                return

        query = text.strip()
        if not query:
            year_val = self.comboSelectYear.currentText()
            if year_val.isdigit():
                self.load_records_for_year(int(year_val))
            return

        # Determine field based on selected radio button
        if self.rbOrigin.isChecked():
            field = "Προέρχεται"
        elif self.rbDest.isChecked():
            field = "Αποστέλλεται"
        elif self.rbOffice.isChecked():
            field = "Γραφείο Διεκπεραίωσης"
        elif self.rbDescInc.isChecked():
            field = "ΠΕΡΙΓΡ. ΕΙΣΕΡΧ."
        elif self.rbDescOut.isChecked():
            field = "ΠΕΡΙΓΡ. ΕΞΕΡΧ."
        else:
            field = "Προέρχεται"

        year_val = self.comboSelectYear.currentText()
        year_filter = int(year_val) if year_val.isdigit() else None
        results = database.get_all_records(year_filter=year_filter, search_field=field, search_query=query)
        self.current_records = [dict(r) for r in results]
        if self.current_records:
            self.current_index = 0
            self.display_record(self.current_records[0])
        else:
            self.current_index = -1
            self.clear_fields()
        self.update_nav_labels()

    def clear_filter(self):
        if not self.check_unsaved_changes():
            return
        self.txtSearchQuery.clear()
        year_val = self.comboSelectYear.currentText()
        if year_val.isdigit():
            self.load_records_for_year(int(year_val))

    # ---------------- ATTACHMENTS ----------------
    def browse_photo(self, target_line_edit):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Επιλογή Συνημμένου Εγγράφου", "",
            "Όλα τα υποστηριζόμενα (*.pdf *.jpg *.jpeg *.png *.bmp *.docx *.xlsx);;Αρχεία PDF (*.pdf);;Εικόνες / Σαρώσεις (*.jpg *.jpeg *.png *.bmp);;Έγγραφα Office (*.docx *.xlsx);;Όλα τα αρχεία (*.*)"
        )
        if file_path:
            dest = database.copy_to_attachments(file_path)
            target_line_edit.setText(dest)

    def open_photo(self, path):
        if not path or not path.strip():
            QMessageBox.warning(self, "Προσοχή", "Δεν έχει καθοριστεί διαδρομή αρχείου για άνοιγμα.")
            return

        full_path = os.path.abspath(path.strip())
        if not os.path.exists(full_path):
            QMessageBox.warning(self, "Προσοχή", f"Το αρχείο δεν βρέθηκε στη διαδρομή:\n{full_path}")
            return

        ext = os.path.splitext(full_path)[1].lower()
        if ext in (".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"):
            # Άνοιγμα με τον ενσωματωμένο προβολέα εγγράφων
            viewer = DocumentViewerDialog(full_path, parent=self, app_icon=self.windowIcon())
            viewer.exec()
        else:
            # Άνοιγμα με την προεπιλεγμένη εφαρμογή του συστήματος (π.χ. Word, Excel)
            os.startfile(full_path)

    # ---------------- PROTOCOL BUTTON COLOR STATE & UNSAVED CHANGES ----------------
    def set_protocol_button_state(self, is_new_or_dirty: bool):
        """
        Updates dirty state and button visuals.
        """
        self.is_dirty = is_new_or_dirty
        self.update_buttons_ui()

    def check_unsaved_changes(self) -> bool:
        """
        Checks if there are unsaved changes before moving away or closing.
        Returns:
            True if it is safe to proceed,
            False if action was cancelled.
        """
        if not self.is_dirty:
            return True

        # If in new mode, check if user actually typed anything
        if self.is_new_mode:
            has_data = bool(
                self.txtDocType.text().strip() or
                self.txtOrigin.text().strip() or
                self.txtDestination.text().strip() or
                self.txtIncomingDesc.toPlainText().strip() or
                self.txtOutgoingDesc.toPlainText().strip() or
                self.txtRemarks.toPlainText().strip() or
                self.txtOffice.text().strip() or
                (self.comboDocClass.currentIndex() != -1 and bool(self.comboDocClass.currentText().strip()))
            )
            if not has_data:
                self.is_dirty = False
                self.is_new_mode = False
                self.is_edit_mode = False
                self.set_protocol_button_state(False)
                return True

        curr_proto = self.txtProtocolNum.text().strip()
        curr_year = self.txtCurrentYear.text().strip()
        proto_label = f"#{curr_proto}/{curr_year}" if curr_proto else "του τρέχοντος πρωτοκόλλου"

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Μη Αποθηκευμένες Αλλαγές")
        msg_box.setText(f"Υπάρχουν μη αποθηκευμένες αλλαγές στο Πρωτόκολλο {proto_label}.\n\nΕπιθυμείτε να τις αποθηκεύσετε πριν συνεχίσετε;")
        msg_box.setIcon(QMessageBox.Icon.Question)

        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Save)

        btn_save = msg_box.button(QMessageBox.StandardButton.Save)
        if btn_save:
            btn_save.setText("Αποθήκευση")
        btn_discard = msg_box.button(QMessageBox.StandardButton.Discard)
        if btn_discard:
            btn_discard.setText("Απόρριψη")
        btn_cancel = msg_box.button(QMessageBox.StandardButton.Cancel)
        if btn_cancel:
            btn_cancel.setText("Ακύρωση")

        ret = msg_box.exec()

        if ret == QMessageBox.StandardButton.Save:
            return self.save_record()
        elif ret == QMessageBox.StandardButton.Discard:
            self.is_dirty = False
            self.is_new_mode = False
            self.is_edit_mode = False
            self.set_protocol_button_state(False)
            return True
        else:
            return False

    def closeEvent(self, event):
        if self.check_unsaved_changes():
            event.accept()
        else:
            event.ignore()

    # ---------------- ADVANCED SEARCH ----------------
    def open_advanced_search(self, target_type, date_field_type):
        dlg = SearchDialog(self, target_type=target_type, date_field_type=date_field_type)
        dlg.exec()

    def show_specific_protocol(self, year, proto_num):
        if not self.check_unsaved_changes():
            return
        idx = self.comboSelectYear.findText(str(year))
        if idx >= 0:
            self.comboSelectYear.setCurrentIndex(idx)
        else:
            self.load_records_for_year(year)

        for i, r in enumerate(self.current_records):
            if r.get("protocol_number") == proto_num:
                self.current_index = i
                self.display_record(r)
                self.update_nav_labels()
                break

    # ---------------- MENU ACTIONS ----------------
    def action_new_year(self):
        if not self.check_unsaved_changes():
            return
        curr_year = datetime.now().year
        years = database.get_years()
        suggested_year = max(years) + 1 if years else curr_year + 1

        new_year, ok = QInputDialog.getInt(
            self, "Εισαγωγή Νέου Έτους", "Εισάγετε το νέο έτος πρωτοκόλλησης:",
            suggested_year, 2000, 2100, 1
        )
        if not ok:
            return

        if new_year in years:
            QMessageBox.information(
                self, "Πληροφορία",
                f"Το έτος {new_year} υπάρχει ήδη στη βάση δεδομένων. Γίνεται μετάβαση στο έτος {new_year}."
            )
            idx = self.comboSelectYear.findText(str(new_year))
            if idx >= 0:
                self.comboSelectYear.setCurrentIndex(idx)
            return

        # Add new year to comboSelectYear in descending order
        all_years = sorted(list(set(years + [new_year])), reverse=True)
        self.comboSelectYear.blockSignals(True)
        self.comboSelectYear.clear()
        for y in all_years:
            self.comboSelectYear.addItem(str(y))
        idx = self.comboSelectYear.findText(str(new_year))
        if idx >= 0:
            self.comboSelectYear.setCurrentIndex(idx)
        self.comboSelectYear.blockSignals(False)

        # Clear form & prepare first record #1 for the new year
        self.current_records = []
        self.current_index = -1
        self.is_new_mode = True
        self.is_edit_mode = True
        self.clear_fields()
        self.txtCurrentYear.setText(str(new_year))
        self.txtProtocolNum.setText("1")
        self.lblNavOf.setText("από 0")
        self.txtNavIndex.setText("*")
        self.set_form_read_only(False)
        self.update_buttons_ui()

        # Reset search dropdown
        self.comboSearchProto.blockSignals(True)
        self.comboSearchProto.clear()
        self.comboSearchProto.addItem("")
        self.comboSearchProto.blockSignals(False)

        QMessageBox.information(
            self, "Νέο Έτος Πρωτοκόλλου",
            f"Το έτος {new_year} ενεργοποιήθηκε επιτυχώς!\nΤο πρώτο πρωτόκολλο για το {new_year} θα λάβει τον αριθμό #1."
        )

    def action_backup(self):
        dest_file, _ = QFileDialog.getSaveFileName(
            self, "Αποθήκευση Αντιγράφου Ασφαλείας", f"backup_protocol_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
            "SQLite Database (*.db)"
        )
        if dest_file:
            try:
                database.create_backup(dest_file)
                QMessageBox.information(self, "Αντίγραφο Ασφαλείας", "Το αντίγραφο δημιουργήθηκε επιτυχώς!")
            except Exception as e:
                QMessageBox.critical(self, "Σφάλμα", f"Αποτυχία δημιουργίας: {e}")

    def action_restore(self):
        if not self.check_unsaved_changes():
            return
        src_file, _ = QFileDialog.getOpenFileName(
            self, "Επιλογή Αντιγράφου για Επαναφορά", "", "SQLite Database (*.db)"
        )
        if src_file:
            confirm = QMessageBox.question(
                self, "Επιβεβαίωση", "Η επαναφορά θα αντικαταστήσει τα τρέχοντα δεδομένα. Συνέχεια;",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    database.restore_backup(src_file)
                    QMessageBox.information(self, "Επαναφορά", "Η επαναφορά ολοκληρώθηκε επιτυχώς!")
                    self.refresh_data()
                except Exception as e:
                    QMessageBox.critical(self, "Σφάλμα", f"Αποτυχία επαναφοράς: {e}")

    def action_export(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Εξαγωγή σε CSV", f"protocol_export_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)"
        )
        if file_path:
            try:
                records = database.get_all_records()
                with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "ID", "Αριθμός Πρωτοκόλλου", "Έτος", "Ημερομηνία", "Κατηγορία",
                        "Ημ. Εισερχομένου", "Είδος Εγγράφου", "Προέλευση", "Περιγραφή Εισερχ.",
                        "Αρχείο Εισερχ.", "Γραφείο", "Διεκπεραιωμένο", "Παρατηρήσεις",
                        "Ημ. Εξερχομένου", "Προορισμός", "Περιγραφή Εξερχ.", "Αρχείο Εξερχ."
                    ])
                    for r in records:
                        writer.writerow([
                            r["id"], r["protocol_number"], r["year"], r["protocol_date"],
                            r["doc_class"], r["incoming_date"], r["doc_type"], r["incoming_origin"],
                            r["incoming_desc"], r["incoming_file"], r["processing_office"],
                            r["completed"], r["remarks"], r["outgoing_date"], r["outgoing_dest"],
                            r["outgoing_desc"], r["outgoing_file"]
                        ])
                QMessageBox.information(self, "Εξαγωγή", "Τα δεδομένα εξήχθησαν επιτυχώς!")
            except Exception as e:
                QMessageBox.critical(self, "Σφάλμα", f"Αποτυχία εξαγωγής: {e}")

    def action_reset_db(self):
        text, ok = QInputDialog.getText(
            self,
            "Διαγραφή και Επαναφορά Βάσης",
            "⚠️ ΠΡΟΣΟΧΗ:\n"
            "Η ενέργεια αυτή θα διαγράψει ΟΛΕΣ τις καταχωρημένες εγγραφές πρωτοκόλλου!\n"
            "Η αρίθμηση θα μηδενιστεί και η βάση θα επανέλθει σε αρχική κενή κατάσταση.\n\n"
            "Πριν τη διαγραφή, θα ληφθεί αυτόματα αντίγραφο ασφαλείας στον φάκελο backups.\n\n"
            "Για να επιβεβαιώσετε, πληκτρολογήστε ακριβώς τη λέξη ΔΙΑΓΡΑΦΗ παρακάτω:"
        )
        if not ok:
            return

        # Normalize Greek word check (handle casing and tonous)
        entered = text.strip().upper().replace("Ή", "Η")
        if entered != "ΔΙΑΓΡΑΦΗ":
            QMessageBox.warning(
                self,
                "Ακύρωση Διαγραφής",
                "Η λέξη επιβεβαίωσης δεν ήταν σωστή (απαιτείται 'ΔΙΑΓΡΑΦΗ').\nΗ διαδικασία ακυρώθηκε χωρίς καμία αλλαγή."
            )
            return

        try:
            database.reset_database()
            self.is_dirty = False
            self.is_edit_mode = False
            self.is_new_mode = False
            self.refresh_data()
            QMessageBox.information(
                self,
                "Επαναφορά Ολοκληρώθηκε",
                "Η βάση δεδομένων διαγράφηκε και επανήλθε επιτυχώς σε αρχική κατάσταση!\n"
                "Όλες οι εγγραφές εκκαθαρίστηκαν και η αρίθμηση ξεκινά από το #1.\n\n"
                "Έχει αποθηκευτεί αυτόματο αντίγραφο ασφαλείας στον φάκελο backups."
            )
        except Exception as e:
            QMessageBox.critical(self, "Σφάλμα", f"Αποτυχία επαναφοράς βάσης: {e}")

    def action_check_updates(self):
        """Χειροκίνητος έλεγχος ενημερώσεων (από μενού)."""
        self.auto_updater.check_for_updates(silent=False)

    def action_about(self):
        QMessageBox.about(
            self, f"Σχετικά με το {__app_name__}",
            f"<h3>{__app_name__}</h3>"
            f"<p><b>Έκδοση:</b> v{__version__}</p>"
            f"<p><b>Αποθετήριο GitHub:</b> {GITHUB_REPO}</p>"
            f"<p><b>Τεχνολογία:</b> Python / PyQt6 / SQLite</p>"
            "<p>Πλήρης σχεδιασμός φόρμας ακριβώς σύμφωνα με το πρότυπο.</p>"
            "<hr>"
            "<p>🔄 <i>Υποστηρίζει αυτόματες ενημερώσεις μέσω GitHub.</i></p>"
        )


def main():
    # Set Windows AppUserModelID so taskbar groups properly and displays the custom app icon
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("cyber.protocol.desktop.1.0")
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    icon_path = get_app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    app_font = app.font()
    app_font.setBold(True)
    app.setFont(app_font)
    app.setStyleSheet("* { font-weight: bold; }")
    window = ProtocolMainWindow()
    if icon_path:
        window.setWindowIcon(QIcon(icon_path))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
