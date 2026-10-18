# ─────────────────────────────────────────────────────────────
#  Ηλεκτρονικό Πρωτόκολλο Εγγράφων — Auto-Updater Core
#  Οδηγία Ασφαλούς Υλοποίησης (Throttling, Cancellation & DLL Protection)
# ─────────────────────────────────────────────────────────────

import os
import sys
import time
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
    """
    Background worker thread: ελέγχει GitHub Releases API για νέα έκδοση.
    Δίνει προτεραιότητα στη λήψη του πλήρους εγκαταστάτη (Inno Setup Installer).
    """
    update_available = pyqtSignal(str, str, str)  # version, download_url, release_notes
    no_update = pyqtSignal()
    check_failed = pyqtSignal(str)

    def run(self):
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(
                api_url,
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "ProtocolApp-Updater"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            latest_tag = data.get("tag_name", "").lstrip("v").strip()
            release_notes = data.get("body", "") or ""

            # Αναζήτηση του προγράμματος εγκατάστασης (Setup .exe)
            download_url = ""
            assets = data.get("assets", [])

            for asset in assets:
                name = asset.get("name", "").lower()
                if name.endswith(".exe") and ("setup" in name or "install" in name):
                    download_url = asset["browser_download_url"]
                    break

            if not latest_tag or not download_url:
                self.no_update.emit()
                return

            # Συγχρονισμός Εκδόσεων: Σημασιολογική σύγκριση για αποτροπή ατέρμονου βρόχου (infinite update loop)
            if Version(latest_tag) > Version(__version__):
                self.update_available.emit(latest_tag, download_url, release_notes)
            else:
                self.no_update.emit()

        except Exception as e:
            self.check_failed.emit(str(e))


class DownloadWorkerThread(QThread):
    """
    Background worker thread λήψης αρχείου:
    - Υπολογισμός ποσοστού (%), MB ληφθέντων/συνολικών και στιγμιαίας ταχύτητας
    - Throttling εκπομπής σημάτων στα ~40ms (25fps) για αποτροπή UI freezes
    - Ασφαλής ακύρωση με άμεση διαγραφή ημιτελών προσωρινών αρχείων
    """
    # progress_updated: percentage (int), downloaded_bytes, total_bytes, speed_bytes_per_sec
    progress_updated = pyqtSignal(int, int, int, float)
    download_finished = pyqtSignal(str)   # filepath
    download_cancelled = pyqtSignal()
    download_failed = pyqtSignal(str)     # error message

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.is_cancelled = False
        self.temp_filepath = None

    def cancel(self):
        """Σηματοδοτεί ασφαλή ακύρωση της λήψης."""
        self.is_cancelled = True

    def run(self):
        self.temp_filepath = None
        try:
            req = urllib.request.Request(
                self.url,
                headers={"User-Agent": "ProtocolApp-Updater"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                total_bytes = int(resp.headers.get("Content-Length", 0))
                temp_dir = tempfile.mkdtemp(prefix="protocol_update_")
                filename = os.path.basename(self.url) or "Protocol_Setup.exe"
                self.temp_filepath = os.path.join(temp_dir, filename)

                downloaded_bytes = 0
                chunk_size = 65536  # 64 KB chunks

                start_time = time.time()
                last_emit_time = 0.0
                speed_window_start = start_time
                speed_window_bytes = 0
                current_speed = 0.0

                with open(self.temp_filepath, "wb") as f:
                    while True:
                        if self.is_cancelled:
                            break

                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        speed_window_bytes += len(chunk)

                        now = time.time()
                        # Υπολογισμός στιγμιαίας ταχύτητας κάθε 0.5 sec
                        window_duration = now - speed_window_start
                        if window_duration >= 0.5:
                            current_speed = speed_window_bytes / window_duration
                            speed_window_bytes = 0
                            speed_window_start = now

                        # Throttling προόδου στα ~40ms (25fps) για ομαλό UI
                        if (now - last_emit_time) >= 0.04 or downloaded_bytes == total_bytes:
                            percent = int(downloaded_bytes * 100 / total_bytes) if total_bytes > 0 else 0
                            self.progress_updated.emit(percent, downloaded_bytes, total_bytes, current_speed)
                            last_emit_time = now

            # Έλεγχος αν ακυρώθηκε
            if self.is_cancelled:
                self._cleanup_temp_file()
                self.download_cancelled.emit()
            else:
                self.download_finished.emit(self.temp_filepath)

        except Exception as e:
            self._cleanup_temp_file()
            if self.is_cancelled:
                self.download_cancelled.emit()
            else:
                self.download_failed.emit(str(e))

    def _cleanup_temp_file(self):
        """Διαγράφει πλήρως τυχόν ημιτελή αρχεία από τον δίσκο."""
        if self.temp_filepath and os.path.exists(self.temp_filepath):
            try:
                os.remove(self.temp_filepath)
                parent_dir = os.path.dirname(self.temp_filepath)
                if os.path.exists(parent_dir):
                    os.rmdir(parent_dir)
            except Exception:
                pass


class UpdateDialog(QDialog):
    """Παράθυρο ειδοποίησης και ασύγχρονης λήψης νέας έκδοσης."""

    def __init__(self, new_version, download_url, release_notes="", parent=None):
        super().__init__(parent)
        self.new_version = new_version
        self.download_url = download_url
        self.worker = None

        self.setWindowTitle("🔄 Διαθέσιμη Ενημέρωση Εφαρμογής")
        self.setFixedWidth(520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # Τίτλος & Έκδοση
        title = QLabel(f"<h3>🆕 Νέα Έκδοση {new_version} Διαθέσιμη!</h3>")
        title.setWordWrap(True)
        layout.addWidget(title)

        info = QLabel(
            f"<p><b>Τρέχουσα έκδοση:</b> v{__version__} &nbsp; ➔ &nbsp; "
            f"<b>Νέα έκδοση:</b> <span style='color: #28a745;'>v{new_version}</span></p>"
        )
        layout.addWidget(info)

        # Release Notes
        if release_notes:
            notes_clean = release_notes.strip()
            if len(notes_clean) > 500:
                notes_clean = notes_clean[:500] + "..."
            notes_box = QLabel(
                f"<div style='background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 4px; padding: 10px;'>"
                f"<b>Τι νέο περιλαμβάνει:</b><br/>{notes_clean}</div>"
            )
            notes_box.setWordWrap(True)
            layout.addWidget(notes_box)

        # Progress Bar & Λεπτομέρειες (κρυμμένα αρχικά)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_details = QLabel("")
        self.lbl_details.setStyleSheet("color: #495057; font-size: 11px;")
        self.lbl_details.setVisible(False)
        layout.addWidget(self.lbl_details)

        # Κουμπιά ενεργειών
        btn_layout = QHBoxLayout()
        self.btn_action = QPushButton("⬇️ Ενημέρωση Τώρα")
        self.btn_action.setStyleSheet(
            "QPushButton { background: #28a745; color: white; font-weight: bold; "
            "padding: 8px 22px; border-radius: 4px; }"
            "QPushButton:hover { background: #218838; }"
        )
        self.btn_action.clicked.connect(self.start_download)

        self.btn_cancel = QPushButton("Αργότερα")
        self.btn_cancel.setStyleSheet("QPushButton { padding: 8px 20px; }")
        self.btn_cancel.clicked.connect(self.on_cancel_or_close)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_action)
        layout.addLayout(btn_layout)

    def start_download(self):
        """Εκκινεί τη λήψη στο background worker thread."""
        self.btn_action.setEnabled(False)
        self.btn_action.setText("⏳ Λήψη σε εξέλιξη...")
        self.btn_cancel.setText("❌ Ακύρωση Λήψης")

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_details.setVisible(True)
        self.lbl_details.setText("Σύνδεση με τον διακομιστή...")

        self.worker = DownloadWorkerThread(self.download_url, parent=self)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.download_finished.connect(self.on_download_finished)
        self.worker.download_cancelled.connect(self.on_download_cancelled)
        self.worker.download_failed.connect(self.on_download_failed)
        self.worker.start()

    def on_progress_updated(self, percent, downloaded, total, speed):
        """Hook προόδου με throttling: υπολογισμός MB και στιγμιαίας ταχύτητας."""
        self.progress_bar.setValue(percent)

        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024) if total > 0 else 0

        if speed >= 1024 * 1024:
            speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
        else:
            speed_str = f"{speed / 1024:.0f} KB/s"

        if total_mb > 0:
            self.lbl_details.setText(
                f"Λήφθηκαν: {downloaded_mb:.1f} MB από {total_mb:.1f} MB ({percent}%) — Ταχύτητα: {speed_str}"
            )
        else:
            self.lbl_details.setText(f"Λήφθηκαν: {downloaded_mb:.1f} MB — Ταχύτητα: {speed_str}")

    def on_download_finished(self, filepath):
        """
        Εκτέλεση Αναβάθμισης & Αποτροπή DLL Crashes:
        1. Ενημερώνει τον χρήστη ΠΡΙΝ ξεκινήσει ο installer (ώστε να μην κλειδώσουν τα αρχεία).
        2. Καθαρίζει ρητά όλες τις μεταβλητές περιβάλλοντος του PyInstaller.
        3. Καλεί τον Inno Setup installer και τερματίζει ΑΜΕΣΑ την εφαρμογή.
        """
        self.lbl_details.setText("✅ Η λήψη ολοκληρώθηκε! Προετοιμασία εγκατάστασης...")

        # Αν δεν τρέχει ως compiled .exe (π.χ. τρέχει από τον κώδικα κατά το development)
        if not getattr(sys, "frozen", False):
            QMessageBox.information(
                self,
                "Δοκιμαστική Λειτουργία (Dev Mode)",
                f"Το πακέτο κατέβηκε επιτυχώς στο:\n{filepath}\n\n"
                "Επειδή τρέχετε από πηγαίο κώδικα, η εγκατάσταση δεν θα εκτελεστεί αυτόματα."
            )
            self.accept()
            return

        # 1. Ενημέρωση χρήστη ΠΡΙΝ ξεκινήσει το Popen (ώστε να μην κλειδώσουν τα αρχεία)
        QMessageBox.information(
            self,
            "Αναβάθμιση έτοιμη",
            "Η λήψη ολοκληρώθηκε! Πατήστε ΟΚ για να κλείσει η εφαρμογή "
            "και να εγκατασταθεί αυτόματα η νέα έκδοση.\n\n"
            "Όλα τα δεδομένα και οι εγγραφές σας παραμένουν ασφαλή."
        )

        try:
            # 2. ΠΛΗΡΗΣ ΚΑΘΑΡΙΣΜΟΣ ΜΕΤΑΒΛΗΤΩΝ ΠΕΡΙΒΑΛΛΟΝΤΟΣ PYINSTALLER
            clean_env = os.environ.copy()
            for k in list(clean_env.keys()):
                if k.startswith(("_MEI", "_PYI", "PYINSTALLER")) or k in ("PYTHONPATH", "PYTHONHOME"):
                    clean_env.pop(k, None)
            clean_env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"

            # 3. Εκτέλεση Inno Setup installer σε σιωπηλή λειτουργία
            subprocess.Popen(
                [filepath, "/SILENT", "/CLOSEAPPLICATIONS", "/NORESTART"],
                env=clean_env,
                cwd=tempfile.gettempdir(),
                shell=False,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )

            # 4. ΑΜΕΣΟΣ τερματισμός της εφαρμογής για απελευθέρωση των αρχείων
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()
            os._exit(0)

        except Exception as e:
            QMessageBox.critical(
                self, "Σφάλμα Εκκίνησης Εγκαταστάτη",
                f"Δεν ήταν δυνατή η εκκίνηση του πακέτου αναβάθμισης:\n{e}\n\n"
                f"Μπορείτε να το εκτελέσετε χειροκίνητα από:\n{filepath}"
            )
            self.accept()

    def on_download_cancelled(self):
        """Ασφαλής ακύρωση: επαναφορά κατάστασης διαλόγου."""
        self.lbl_details.setText("⚠️ Η λήψη ακυρώθηκε. Τα προσωρινά αρχεία διαγράφηκαν.")
        self.progress_bar.setVisible(False)
        self.btn_action.setEnabled(True)
        self.btn_action.setText("⬇️ Ενημέρωση Τώρα")
        self.btn_cancel.setText("Κλείσιμο")

    def on_download_failed(self, error):
        """Αποτυχία λήψης."""
        self.lbl_details.setText(f"❌ Σφάλμα λήψης: {error}")
        self.btn_action.setEnabled(True)
        self.btn_action.setText("Δοκιμάστε Ξανά")
        self.btn_cancel.setText("Κλείσιμο")

    def on_cancel_or_close(self):
        """Χειρισμός ακύρωσης / κλεισίματος."""
        if self.worker and self.worker.isRunning():
            self.lbl_details.setText("⏳ Ακύρωση σύνδεσης και καθαρισμός αρχείων...")
            self.worker.cancel()
            self.worker.wait(2000)
        self.reject()

    def closeEvent(self, event):
        """Αποτροπή ορφανών threads κατά το κλείσιμο του παραθύρου."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)
        event.accept()


class AutoUpdater:
    """
    Κεντρική κλάση διαχείρισης αυτόματων ενημερώσεων.
    """

    def __init__(self, parent=None):
        self.parent = parent
        self.check_thread = None
        self.silent = True

    def check_for_updates(self, silent=True):
        """Εκκινεί background έλεγχο στο GitHub Releases API."""
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
                f"Χρησιμοποιείτε την τελευταία έκδοση (v{__version__}).\n"
                "Δεν υπάρχει διαθέσιμη νέα ενημέρωση."
            )

    def _on_check_failed(self, error):
        if not self.silent:
            QMessageBox.warning(
                self.parent,
                "Σφάλμα Ελέγχου",
                f"Δεν ήταν δυνατός ο έλεγχος ενημερώσεων:\n{error}"
            )
