# ─────────────────────────────────────────────────────────────
#  Ηλεκτρονικό Πρωτόκολλο Εγγράφων — Auto-Updater
#  Ελέγχει το GitHub Releases API για νέες εκδόσεις
#  και ειδοποιεί τον χρήστη αθόρυβα.
# ─────────────────────────────────────────────────────────────

import os
import sys
import json
import tempfile
import subprocess
import urllib.request
import urllib.error
from packaging.version import Version

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox
)

from version import __version__, GITHUB_REPO


class UpdateCheckThread(QThread):
    """Background thread: ελέγχει GitHub Releases API για νέα έκδοση."""
    update_available = pyqtSignal(str, str, str)  # version, download_url, release_notes
    no_update = pyqtSignal()
    check_failed = pyqtSignal(str)

    def run(self):
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(
                api_url,
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "ProtocolApp"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            latest_tag = data.get("tag_name", "").lstrip("v")
            release_notes = data.get("body", "") or ""

            # Βρες το installer asset (.exe)
            download_url = ""
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if name.endswith(".exe") and "setup" in name:
                    download_url = asset["browser_download_url"]
                    break

            if not latest_tag or not download_url:
                self.no_update.emit()
                return

            # Σύγκριση εκδόσεων
            if Version(latest_tag) > Version(__version__):
                self.update_available.emit(latest_tag, download_url, release_notes)
            else:
                self.no_update.emit()

        except Exception as e:
            self.check_failed.emit(str(e))


class DownloadThread(QThread):
    """Κατεβάζει το νέο installer με progress reporting."""
    progress = pyqtSignal(int)          # ποσοστό (0-100)
    download_finished = pyqtSignal(str)  # filepath
    download_failed = pyqtSignal(str)    # error message

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            req = urllib.request.Request(
                self.url,
                headers={"User-Agent": "ProtocolApp"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                temp_dir = tempfile.mkdtemp(prefix="protocol_update_")
                filename = os.path.basename(self.url)
                filepath = os.path.join(temp_dir, filename)

                downloaded = 0
                chunk_size = 65536  # 64 KB
                with open(filepath, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self.progress.emit(int(downloaded * 100 / total))

            self.download_finished.emit(filepath)

        except Exception as e:
            self.download_failed.emit(str(e))


class UpdateDialog(QDialog):
    """Παράθυρο ειδοποίησης νέας έκδοσης."""

    def __init__(self, new_version, download_url, release_notes="", parent=None):
        super().__init__(parent)
        self.new_version = new_version
        self.download_url = download_url
        self.download_thread = None
        self.setWindowTitle("🔄 Διαθέσιμη Ενημέρωση")
        self.setFixedWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Τίτλος
        title = QLabel(f"<h3>🆕 Νέα Έκδοση {new_version} Διαθέσιμη!</h3>")
        title.setWordWrap(True)
        layout.addWidget(title)

        # Τρέχουσα & Νέα
        info = QLabel(
            f"<p><b>Τρέχουσα έκδοση:</b> {__version__}<br/>"
            f"<b>Νέα έκδοση:</b> {new_version}</p>"
        )
        layout.addWidget(info)

        # Release Notes (αν υπάρχουν)
        if release_notes:
            notes_text = release_notes[:500]  # Κόβουμε αν είναι πολύ μεγάλο
            notes = QLabel(f"<p><b>Τι νέο φέρνει:</b></p><p>{notes_text}</p>")
            notes.setWordWrap(True)
            layout.addWidget(notes)

        # Progress bar (κρυμμένο αρχικά)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

        # Κουμπιά
        btn_layout = QHBoxLayout()
        self.btn_update = QPushButton("⬇️ Ενημέρωση Τώρα")
        self.btn_update.setStyleSheet(
            "QPushButton { background: #28a745; color: white; font-weight: bold; "
            "padding: 8px 20px; border-radius: 4px; }"
            "QPushButton:hover { background: #218838; }"
        )
        self.btn_update.clicked.connect(self.start_download)

        self.btn_later = QPushButton("Αργότερα")
        self.btn_later.setStyleSheet("QPushButton { padding: 8px 20px; }")
        self.btn_later.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_later)
        btn_layout.addWidget(self.btn_update)
        layout.addLayout(btn_layout)

    def start_download(self):
        self.btn_update.setEnabled(False)
        self.btn_later.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setVisible(True)
        self.lbl_status.setText("⏳ Λήψη ενημέρωσης...")

        self.download_thread = DownloadThread(self.download_url)
        self.download_thread.progress.connect(self.progress_bar.setValue)
        self.download_thread.download_finished.connect(self.on_download_finished)
        self.download_thread.download_failed.connect(self.on_download_failed)
        self.download_thread.start()

    def on_download_finished(self, filepath):
        self.lbl_status.setText("✅ Η λήψη ολοκληρώθηκε! Εκκίνηση εγκατάστασης...")
        try:
            # Εκτέλεση του installer σε σιωπηλή λειτουργία
            subprocess.Popen([filepath, "/SILENT", "/RESTARTAPPLICATIONS"], shell=False)
            # Κλείσιμο τρέχουσας εφαρμογής
            QMessageBox.information(
                self,
                "Ενημέρωση",
                "Η ενημέρωση θα εγκατασταθεί τώρα.\n"
                "Η εφαρμογή θα κλείσει και θα επανεκκινήσει αυτόματα."
            )
            sys.exit(0)
        except Exception as e:
            QMessageBox.warning(
                self, "Σφάλμα",
                f"Δεν ήταν δυνατή η εκκίνηση του installer:\n{e}\n\n"
                f"Μπορείτε να τον εκτελέσετε χειροκίνητα:\n{filepath}"
            )
            self.accept()

    def on_download_failed(self, error):
        self.lbl_status.setText(f"❌ Σφάλμα λήψης: {error}")
        self.btn_update.setEnabled(True)
        self.btn_later.setEnabled(True)


class AutoUpdater:
    """
    Κεντρική κλάση auto-updater.
    Χρήση:
        updater = AutoUpdater(parent_window)
        updater.check_for_updates()           # αθόρυβα στο παρασκήνιο
        updater.check_for_updates(silent=False) # χειροκίνητα (εμφανίζει μήνυμα αν δεν υπάρχει ενημέρωση)
    """

    def __init__(self, parent=None):
        self.parent = parent
        self.check_thread = None
        self.silent = True

    def check_for_updates(self, silent=True):
        """Εκκινεί background έλεγχο ενημερώσεων."""
        self.silent = silent
        self.check_thread = UpdateCheckThread()
        self.check_thread.update_available.connect(self._on_update_available)
        self.check_thread.no_update.connect(self._on_no_update)
        self.check_thread.check_failed.connect(self._on_check_failed)
        self.check_thread.start()

    def _on_update_available(self, version, url, notes):
        dlg = UpdateDialog(version, url, notes, parent=self.parent)
        dlg.exec()

    def _on_no_update(self):
        if not self.silent:
            QMessageBox.information(
                self.parent,
                "Έλεγχος Ενημερώσεων",
                f"Χρησιμοποιείτε την τελευταία έκδοση ({__version__}).\n"
                "Δεν υπάρχει διαθέσιμη ενημέρωση."
            )

    def _on_check_failed(self, error):
        if not self.silent:
            QMessageBox.warning(
                self.parent,
                "Σφάλμα Ελέγχου",
                f"Δεν ήταν δυνατός ο έλεγχος ενημερώσεων:\n{error}"
            )
