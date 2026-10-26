"""
Μοντέλα Δεδομένων Πρωτοκόλλου (Domain Models)
"""

from dataclasses import dataclass, asdict, field
from enum import Enum, auto
from typing import Optional, Dict, Any


class RecordMode(Enum):
    """Κατάσταση λειτουργίας φόρμας."""
    VIEW = auto()
    EDIT = auto()
    NEW = auto()


class DocumentClass:
    """Κατηγορίες διακίνησης εγγράφων."""
    INCOMING = "ΕΙΣΕΡΧΟΜΕΝΑ"
    OUTGOING = "ΕΞΕΡΧΟΜΕΝΑ"
    WITH_REPLY = "ΜΕ ΑΠΑΝΤΗΣΗ"
    BOTH = "ΕΙΣΕΡΧΟΜΕΝΟ & ΕΞΕΡΧΟΜΕΝΟ"

    ALL = [INCOMING, OUTGOING, WITH_REPLY, BOTH]


@dataclass
class ProtocolRecord:
    """Αναπαράσταση μίας εγγραφής πρωτοκόλλου."""
    protocol_number: int = 0
    year: int = 0
    id: Optional[int] = None
    protocol_date: str = ""
    doc_class: str = ""
    incoming_date: str = ""
    doc_type: str = ""
    incoming_origin: str = ""
    incoming_desc: str = ""
    incoming_file: str = ""
    processing_office: str = ""
    archive_folder: str = ""
    completed: int = 0
    remarks: str = ""
    outgoing_date: str = ""
    outgoing_dest: str = ""
    outgoing_desc: str = ""
    outgoing_file: str = ""
    extra_data: str = "{}"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProtocolRecord":
        """Δημιουργεί αντικείμενο ProtocolRecord από λεξικό (π.χ. αποτέλεσμα SQLite query)."""
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        
        # Ασφαλής μετατροπή τύπων
        if "protocol_number" in filtered:
            try:
                filtered["protocol_number"] = int(filtered["protocol_number"] or 0)
            except (ValueError, TypeError):
                filtered["protocol_number"] = 0

        if "year" in filtered:
            try:
                filtered["year"] = int(filtered["year"] or 0)
            except (ValueError, TypeError):
                filtered["year"] = 0

        if "completed" in filtered:
            try:
                filtered["completed"] = int(filtered["completed"] or 0)
            except (ValueError, TypeError):
                filtered["completed"] = 0

        return cls(**filtered)

    @classmethod
    def from_row(cls, row: Any) -> "ProtocolRecord":
        """Δημιουργεί αντικείμενο από sqlite3.Row."""
        return cls.from_dict(dict(row))

    def to_dict(self) -> Dict[str, Any]:
        """Μετατρέπει την εγγραφή σε λεξικό."""
        return asdict(self)
