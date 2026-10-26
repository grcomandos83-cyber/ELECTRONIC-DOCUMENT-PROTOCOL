"""
Υπηρεσία Διαχείρισης Συνημμένων Αρχείων (Attachment Service)
"""

import os
import shutil
from datetime import datetime
from typing import Optional
from app.config import ATTACHMENTS_DIR


class AttachmentService:
    """Παρέχει λειτουργίες αντιγραφής, επαλήθευσης και ανοίγματος συνημμένων εγγράφων."""

    SUPPORTED_PREVIEW_EXTENSIONS = {
        ".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"
    }

    FILE_DIALOG_FILTERS = (
        "Όλα τα υποστηριζόμενα (*.pdf *.jpg *.jpeg *.png *.bmp *.docx *.xlsx);;"
        "Αρχεία PDF (*.pdf);;"
        "Εικόνες / Σαρώσεις (*.jpg *.jpeg *.png *.bmp);;"
        "Έγγραφα Office (*.docx *.xlsx);;"
        "Όλα τα αρχεία (*.*)"
    )

    @staticmethod
    def copy_to_attachments(source_path: str) -> str:
        """
        Αντιγράφει ένα εξωτερικό αρχείο στον ασφαλή κατάλογο attachments/
        προσθέτοντας μοναδικό χρονικό πρόθεμα (timestamp) για αποφυγή συγκρούσεων ονομάτων.
        Επιστρέφει την πλήρη διαδρομή του νέου αρχείου.
        """
        if not source_path or not os.path.exists(source_path):
            return ""

        if not os.path.exists(ATTACHMENTS_DIR):
            os.makedirs(ATTACHMENTS_DIR, exist_ok=True)

        filename = os.path.basename(source_path)
        unique_prefix = datetime.now().strftime("%Y%m%d%H%M%S_")
        dest_filename = unique_prefix + filename
        dest_path = os.path.join(ATTACHMENTS_DIR, dest_filename)

        shutil.copy2(source_path, dest_path)
        return dest_path

    @staticmethod
    def resolve_path(file_path: str) -> Optional[str]:
        """
        Επαληθεύει εάν το αρχείο υπάρχει και επιστρέφει την απόλυτη διαδρομή του,
        διαφορετικά επιστρέφει None.
        """
        if not file_path or not file_path.strip():
            return None

        full_path = os.path.abspath(file_path.strip())
        if os.path.exists(full_path):
            return full_path

        # Εναλλακτικός έλεγχος εντός του φακέλου attachments
        alt_path = os.path.join(ATTACHMENTS_DIR, os.path.basename(file_path.strip()))
        if os.path.exists(alt_path):
            return alt_path

        return None

    @classmethod
    def can_preview_internally(cls, file_path: str) -> bool:
        """Ελέγχει αν το αρχείο υποστηρίζει ενσωματωμένη προεπισκόπηση (PDF/Εικόνες)."""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.SUPPORTED_PREVIEW_EXTENSIONS

    @staticmethod
    def open_with_default_application(file_path: str):
        """Ανοίγει το αρχείο με την προεπιλεγμένη εφαρμογή του λειτουργικού συστήματος."""
        resolved = AttachmentService.resolve_path(file_path)
        if not resolved:
            raise FileNotFoundError(f"Το αρχείο δεν βρέθηκε: {file_path}")

        # Windows native file launch
        os.startfile(resolved)
