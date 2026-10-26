"""
Υπηρεσία Αντιγράφων Ασφαλείας, Επαναφοράς και Εξαγωγής (Backup & Export Service)
"""

import os
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional

import database
from app.config import DB_FILE


class BackupService:
    """Διαχειρίζεται τη δημιουργία/επαναφορά αντιγράφων ασφαλείας, εξαγωγές και καθαρισμό βάσης."""

    CSV_HEADERS = [
        "ID", "Αριθμός Πρωτοκόλλου", "Έτος", "Ημερομηνία", "Κατηγορία",
        "Ημ. Εισερχομένου", "Είδος Εγγράφου", "Προέλευση", "Περιγραφή Εισερχ.",
        "Αρχείο Εισερχ.", "Γραφείο", "Φάκελος Αρχειοθέτησης", "Διεκπεραιωμένο", "Παρατηρήσεις",
        "Ημ. Εξερχομένου", "Προορισμός", "Περιγραφή Εξερχ.", "Αρχείο Εξερχ."
    ]

    @staticmethod
    def get_default_backup_filename() -> str:
        """Επιστρέφει προτεινόμενο όνομα αρχείου backup με τρέχουσα ημερομηνία/ώρα."""
        return f"backup_protocol_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

    @staticmethod
    def get_default_export_filename() -> str:
        """Επιστρέφει προτεινόμενο όνομα αρχείου εξαγωγής CSV."""
        return f"protocol_export_{datetime.now().strftime('%Y%m%d')}.csv"

    @staticmethod
    def create_backup(dest_path: str) -> bool:
        """
        Δημιουργεί αντίγραφο ασφαλείας του αρχείου βάσης δεδομένων στον προορισμό dest_path.
        """
        return database.create_backup(dest_path)

    @staticmethod
    def restore_backup(src_path: str) -> bool:
        """
        Επαναφέρει τη βάση δεδομένων από το αρχείο src_path με ασφάλεια (auto-rollback σε περίπτωση σφάλματος).
        """
        return database.restore_backup(src_path)

    @staticmethod
    def export_to_csv(file_path: str, records: Optional[List[Dict[str, Any]]] = None) -> int:
        """
        Εξάγει εγγραφές σε αρχείο CSV με σωστή κωδικοποίηση utf-8-sig για άνοιγμα σε Excel.
        Επιστρέφει το πλήθος των εγγραφών που εξήχθησαν.
        """
        if records is None:
            records = database.get_all_records()

        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(BackupService.CSV_HEADERS)
            for r in records:
                writer.writerow([
                    r.get("id", ""),
                    r.get("protocol_number", ""),
                    r.get("year", ""),
                    r.get("protocol_date", ""),
                    r.get("doc_class", ""),
                    r.get("incoming_date", ""),
                    r.get("doc_type", ""),
                    r.get("incoming_origin", ""),
                    r.get("incoming_desc", ""),
                    r.get("incoming_file", ""),
                    r.get("processing_office", ""),
                    r.get("archive_folder", ""),
                    r.get("completed", 0),
                    r.get("remarks", ""),
                    r.get("outgoing_date", ""),
                    r.get("outgoing_dest", ""),
                    r.get("outgoing_desc", ""),
                    r.get("outgoing_file", "")
                ])
        return len(records)

    @staticmethod
    def reset_database() -> bool:
        """
        Δημιουργεί αυτόματο safety backup και μηδενίζει τη βάση δεδομένων.
        """
        return database.reset_database()
