# 🏛️ Πλάνο Σταδιακής Αναδιοργάνωσης (Refactoring Plan)
## «Ηλεκτρονικό Πρωτόκολλο Εγγράφων»

> [!IMPORTANT]
> **Στόχος:** Μετατροπή της μονολιθικής υλοποίησης (~1200+ γραμμές στο `main.py`) σε μια καθαρή, αρθρωτή (modular) αρχιτεκτονική **χωρίς διακοπή της λειτουργικότητας** και **χωρίς ρίσκο για το packaging (PyInstaller / Inno Setup)**.

---

## 🧭 Σύγκριση Αρχιτεκτονικής

```mermaid
graph TD
    subgraph Πριν (Monolithic)
        M[main.py - 1200+ lines] --> DB[(database.py)]
        M --> UI[ui_protocol_form.py]
        M --> Dlg[search_dialog.py]
        M --> Upd[updater.py]
        M --> Vw[document_viewer.py]
    end

    subgraph Μετά (Layered Architecture)
        EP[main.py: Entry Point] --> MW[app.ui.main_window]
        MW --> SVC[app.services]
        MW --> DLG[app.ui.dialogs]
        SVC --> REPO[app.database]
        SVC --> CFG[app.config]
        REPO --> DB2[(SQLite Database)]
        SVC --> MOD[app.models]
    end
```

---

## 📋 Ανάλυση των 5 Φάσεων Υλοποίησης

```carousel
### 🏗️ Φάση 1: Θεμέλια & Configuration
- **Δημιουργία δομής πακέτου:** Φάκελος `app/` με όλα τα sub-packages (`config`, `models`, `services`, `database`, `ui`).
- **`app/config.py`:** Συγκέντρωση των paths (`BASE_DIR`, `DB_FILE`, `ATTACHMENTS_DIR`, `BACKUPS_DIR`), του κλειδώματος τρέχοντος καταλόγου (frozen path fix), των σταθερών και της έκδοσης.
- **`app/models/protocol.py`:** Ορισμός του `ProtocolRecord` (dataclass) και των καταστάσεων φόρμας (`RecordMode`: VIEW, EDIT, NEW) ώστε να απαλειφθούν τα "μαγικά" strings και dictionaries.
- **Κριτήριο Επαλήθευσης:** Η εφαρμογή τρέχει κανονικά, το `config.py` εισάγεται χωρίς σφάλματα.
<!-- slide -->
### 💾 Φάση 2: Υπηρεσίες Αρχείων, Backup & Εργαλείων Βάσης
- **`app/services/attachment_service.py`:**
  - Αντιγραφή αρχείων στο `attachments/`
  - Εύρεση εικονιδίων, άνοιγμα με native viewer ή default OS πρόγραμμα
  - Υποστηριζόμενα extensions (`.pdf`, `.jpg`, `.png`, `.docx`, κ.λπ.)
- **`app/services/backup_service.py`:**
  - Δημιουργία backup (zip / db)
  - Επαναφορά βάσης (restore)
  - Εξαγωγή σε CSV με σωστή κωδικοποίηση utf-8-sig
  - Μηδενισμός βάσης (reset)
- **Κριτήριο Επαλήθευσης:** Οι λειτουργίες του μενού «Εργαλεία» και τα συνημμένα καλούν τις ανεξάρτητες υπηρεσίες.
<!-- slide -->
### ⚙️ Φάση 3: Υπηρεσία Πρωτοκόλλου & Business Logic
- **`app/services/protocol_service.py`:**
  - Validation πεδίων (έλεγχος υποχρεωτικών, έγκυρων ημερομηνιών, κ.λπ.)
  - Υπολογισμός επόμενου αριθμού πρωτοκόλλου για νέο έτος / τρέχον έτος
  - Διαχείριση dirty state (έλεγχος αν υπάρχουν μη αποθηκευμένες αλλαγές)
  - Συντονισμός αποθήκευσης (Save New vs Update Existing)
- **Κριτήριο Επαλήθευσης:** Το `main.py` δεν περιέχει πλέον λογική SQL ή validation checks, αλλά αναθέτει τις ενέργειες στο service.
<!-- slide -->
### 🖥️ Φάση 4: Απομόνωση UI (Main Window & Dialogs)
- **`app/ui/main_window.py`:** Μεταφορά της κλάσης `ProtocolMainWindow` στο δικό της module.
  - Εστίαση αποκλειστικά σε: signals/slots, αλλαγές εμφάνισης (read-only/edit styling), navigation κουμπιά.
- **`app/ui/dialogs/`:** Μετακίνηση των `search_dialog.py` και `document_viewer.py` στο νέο namespace.
- **Κριτήριο Επαλήθευσης:** Καθαρός διαχωρισμός του κώδικα διεπαφής από τις υπόλοιπες λειτουργίες.
<!-- slide -->
### 🚀 Φάση 5: Thin Entry Point & Packaging Verification
- **`main.py`:** Συρρίκνωση σε ~15-20 γραμμές (αρχικοποίηση `QApplication`, ορισμός DPI scaling/theme, άνοιγμα `ProtocolMainWindow`).
- **`build.spec` & `installer.iss`:** Επιβεβαίωση συμβατότητας (imports, hiddenimports, paths) ώστε η συσκευασία PyInstaller και Inno Setup να συνεχίσει να λειτουργεί απρόσκοπτα.
- **Τελικός Έλεγχος:** Δοκιμή εκτέλεσης, έλεγχος λειτουργιών και build check.
```

---

## 📊 Πίνακας Παραδοτέων ανά Φάση

| Φάση | Νέα / Τροποποιημένα Αρχεία | Κύρια Ευθύνη | Εκτιμώμενη Μείωση Γραμμών στο main.py |
| :--- | :--- | :--- | :--- |
| **Φάση 1** | `app/__init__.py`<br>`app/config.py`<br>`app/models/protocol.py` | Ρυθμίσεις, paths, σταθερές, dataclasses | ~50 γραμμές |
| **Φάση 2** | `app/services/attachment_service.py`<br>`app/services/backup_service.py` | Backup, restore, CSV export, διαχείριση αρχείων | ~250 γραμμές |
| **Φάση 3** | `app/services/protocol_service.py` | Validation, υπολογισμός αριθμού, save/update logic | ~250 γραμμές |
| **Φάση 4** | `app/ui/main_window.py`<br>`app/ui/dialogs/` | Καθαρό UI wiring, πλοήγηση, signals & slots | Μεταφορά όλου του window (~600 γραμμές) |
| **Φάση 5** | `main.py`<br>`build.spec` | Καθαρό Entry point (~20 γραμμές) & packaging verification | Το `main.py` μένει ~20 γραμμές |

---

> [!TIP]
> **Στρατηγική Ασφάλειας:** Κάθε φάση υλοποιείται, ελέγχεται και κατοχυρώνεται ξεχωριστά, διασφαλίζοντας ότι η εφαρμογή παραμένει συνεχώς λειτουργική.
