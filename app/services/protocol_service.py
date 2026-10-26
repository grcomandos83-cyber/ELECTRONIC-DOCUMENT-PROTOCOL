"""
Υπηρεσία Επιχειρησιακής Λογικής Πρωτοκόλλου (Protocol Service)
"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

import database
from app.models.protocol import ProtocolRecord, DocumentClass


class ValidationError(Exception):
    """Εξαίρεση που εγείρεται κατά τον έλεγχο εγκυρότητας πεδίων."""
    def __init__(self, message: str, missing_fields: Optional[List[str]] = None, target_widget_hint: Optional[str] = None):
        super().__init__(message)
        self.missing_fields = missing_fields or []
        self.target_widget_hint = target_widget_hint


class ProtocolService:
    """Διαχειρίζεται τους επιχειρησιακούς κανόνες, το validation και τη διακίνηση εγγραφών πρωτοκόλλου."""

    @staticmethod
    def validate(record: ProtocolRecord) -> None:
        """
        Ελέγχει τους επιχειρησιακούς κανόνες εγκυρότητας:
        1. Επιλογή κατηγορίας (ΕΙΣΕΡΧΟΜΕΝΟ / ΕΞΕΡΧΟΜΕΝΟ κ.λπ.)
        2. Υποχρεωτικά πεδία για εισερχόμενα έγγραφα (Είδος εγγράφου & Προέλευση)
        """
        doc_class = (record.doc_class or "").strip()
        if not doc_class:
            raise ValidationError(
                "Επιλέξτε ΕΙΣΕΡΧΟΜΕΝΟ ή ΕΞΕΡΧΟΜΕΝΟ",
                target_widget_hint="comboDocClass"
            )

        # Για εισερχόμενα έγγραφα, απαιτούνται Είδος Εγγράφου και Υπηρεσία Προέλευσης
        if doc_class in ("ΕΙΣΕΡΧΟΜΕΝΟ", "ΕΙΣΕΡΧΟΜΕΝΑ"):
            missing = []
            hint = None
            if not record.doc_type or not record.doc_type.strip():
                missing.append("ΕΙΔΟΣ ΕΓΓΡΑΦΟΥ")
                hint = "txtDocType"
            if not record.incoming_origin or not record.incoming_origin.strip():
                missing.append("ΥΠΗΡΕΣΙΑ ΠΟΥ ΠΡΟΕΡΧΕΤΑΙ")
                if not hint:
                    hint = "txtOrigin"

            if missing:
                bullet_list = "\n• " + "\n• ".join(missing)
                raise ValidationError(
                    f"Για τα ΕΙΣΕΡΧΟΜΕΝΑ, τα παρακάτω πεδία είναι υποχρεωτικά:{bullet_list}",
                    missing_fields=missing,
                    target_widget_hint=hint
                )

    @staticmethod
    def get_next_protocol_number(year: int) -> int:
        """Επιστρέφει τον επόμενο διαθέσιμο αριθμό πρωτοκόλλου για το δοθέν έτος."""
        return database.get_next_protocol_number(year)

    @staticmethod
    def get_years() -> List[int]:
        """Επιστρέφει λίστα με τα έτη που υπάρχουν στη βάση, συμπεριλαμβανομένου του τρέχοντος."""
        return database.get_years()

    @staticmethod
    def get_archive_folders() -> List[str]:
        """Επιστρέφει όλους τους μοναδικούς φακέλους αρχειοθέτησης."""
        return database.get_archive_folders()

    @staticmethod
    def get_records_by_year(year: int) -> List[ProtocolRecord]:
        """Ανακτά όλες τις εγγραφές για το επιλεγμένο έτος ως αντικείμενα ProtocolRecord."""
        raw_rows = database.get_all_records(year_filter=year)
        return [ProtocolRecord.from_dict(dict(r)) for r in raw_rows]

    @staticmethod
    def search_records(year_filter: Optional[int], search_field: str, query: str) -> List[ProtocolRecord]:
        """Εκτελεί αναζήτηση με κριτήρια και επιστρέφει αντικείμενα ProtocolRecord."""
        raw_rows = database.get_all_records(year_filter=year_filter, search_field=search_field, search_query=query)
        return [ProtocolRecord.from_dict(dict(r)) for r in raw_rows]

    @classmethod
    def save(cls, record: ProtocolRecord, is_new: bool) -> Tuple[ProtocolRecord, bool]:
        """
        Επικυρώνει και αποθηκεύει την εγγραφή στη βάση δεδομένων.
        
        Επιστρέφει:
            (ProtocolRecord, is_new_record_created)
        """
        cls.validate(record)

        data = record.to_dict()

        if is_new:
            new_id, assigned_num = database.insert_record(data)
            record.id = new_id
            record.protocol_number = assigned_num
            return record, True
        else:
            if not record.id:
                raise ValueError("Δεν μπορεί να γίνει ενημέρωση εγγραφής χωρίς έγκυρο ID.")
            database.update_record(record.id, data)
            return record, False
