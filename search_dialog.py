import os
import csv
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog
)
from PyQt6.QtCore import QDate, Qt

from ui_search_dialog import Ui_SearchDialog
import database


class SearchDialog(QDialog, Ui_SearchDialog):
    def __init__(self, parent=None, target_type="ΕΙΣΕΡΧΟΜΕΝΑ", date_field_type="protocol_date"):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_window = parent
        self.target_type = target_type          # "ΕΙΣΕΡΧΟΜΕΝΑ" or "ΕΞΕΡΧΟΜΕΝΑ"
        self.date_field_type = date_field_type  # "protocol_date" or "doc_date"
        self.results = []

        # Ensure all fields and labels are bold
        bold_font = self.font()
        bold_font.setBold(True)
        self.setFont(bold_font)
        for w in self.findChildren(QWidget):
            wf = w.font()
            wf.setBold(True)
            w.setFont(wf)

        # Setup table
        self.setup_table()

        # Populate years
        years = database.get_years()
        self.comboFilterYear.clear()
        self.comboFilterYear.addItem("Όλα")
        for y in sorted(years, reverse=True):
            self.comboFilterYear.addItem(str(y))

        # Default dates: from Jan 1st of current year to today
        today = QDate.currentDate()
        self.dateFrom.setDate(QDate(today.year(), 1, 1))
        self.dateTo.setDate(today)

        # Configure title and mode
        self.configure_mode()

        # Connect signals
        self.btnSearch.clicked.connect(self.perform_search)
        self.btnReset.clicked.connect(self.reset_filters)
        self.btnExport.clicked.connect(self.export_results)
        self.btnOpenSelected.clicked.connect(self.open_selected)
        self.btnClose.clicked.connect(self.accept)
        self.tableResults.cellDoubleClicked.connect(self.on_row_double_clicked)

        # Initial search
        self.perform_search()

    def configure_mode(self):
        target_label = "ΕΙΣΕΡΧΟΜΕΝΑ" if self.target_type == "ΕΙΣΕΡΧΟΜΕΝΑ" else "ΕΞΕΡΧΟΜΕΝΑ"
        if self.date_field_type == "protocol_date":
            date_label = "ΜΕ ΗΜΕΡΟΜΗΝΙΑ ΠΡΩΤΟΚΟΛΛΗΣΗΣ"
        else:
            date_label = "ΜΕ ΗΜΕΡΟΜΗΝΙΑ ΕΓΓΡΑΦΟΥ"

        self.setWindowTitle(f"Σύνθετη Αναζήτηση - {target_label} ({date_label})")
        self.lblModeTitle.setText(f"Κριτήρια Αναζήτησης: {target_label} — {date_label}")

        if self.target_type == "ΕΞΕΡΧΟΜΕΝΑ":
            self.lblFilterEntity.setText("Υπηρεσία Αποστολής:")
            self.txtFilterEntity.setPlaceholderText("Υπηρεσία που αποστέλλεται...")
        else:
            self.lblFilterEntity.setText("Υπηρεσία Προέλευσης:")
            self.txtFilterEntity.setPlaceholderText("Υπηρεσία που προέρχεται...")

    def setup_table(self):
        headers = [
            "Α/Α Πρωτ.", "Έτος", "Ημ. Πρωτοκόλλου", "Κατηγορία",
            "Ημ. Εγγράφου", "Είδος Εγγράφου", "Υπηρεσία", "Περιγραφή", "Διεκπεραιωμένο"
        ]
        self.tableResults.setColumnCount(len(headers))
        self.tableResults.setHorizontalHeaderLabels(headers)

        header = self.tableResults.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)

    def get_actual_date_field(self):
        if self.date_field_type == "protocol_date":
            return "protocol_date"
        else:
            return "incoming_date" if self.target_type == "ΕΙΣΕΡΧΟΜΕΝΑ" else "outgoing_date"

    def perform_search(self):
        date_field = self.get_actual_date_field()
        start_date = self.dateFrom.date().toString("yyyy-MM-dd")
        end_date = self.dateTo.date().toString("yyyy-MM-dd")
        year_filter = self.comboFilterYear.currentText()

        entity_filter = self.txtFilterEntity.text().strip()
        doc_type_filter = self.txtFilterDocType.text().strip()
        desc_filter = self.txtFilterDesc.text().strip()

        self.results = database.search_advanced(
            target_type=self.target_type,
            date_field=date_field,
            start_date=start_date,
            end_date=end_date,
            year_filter=year_filter,
            entity_filter=entity_filter,
            doc_type_filter=doc_type_filter,
            desc_filter=desc_filter
        )

        self.populate_table(self.results)

    def populate_table(self, records):
        self.tableResults.setRowCount(0)
        self.tableResults.setRowCount(len(records))

        for row, r in enumerate(records):
            # 0: Protocol number
            p_num = str(r.get("protocol_number", ""))
            item_num = QTableWidgetItem(p_num)
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tableResults.setItem(row, 0, item_num)

            # 1: Year
            yr = str(r.get("year", ""))
            item_year = QTableWidgetItem(yr)
            item_year.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tableResults.setItem(row, 1, item_year)

            # 2: Protocol date
            p_date = database.db_to_ui_date(r.get("protocol_date"))
            item_pdate = QTableWidgetItem(p_date)
            item_pdate.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tableResults.setItem(row, 2, item_pdate)

            # 3: Category
            item_cat = QTableWidgetItem(r.get("doc_class") or "")
            item_cat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tableResults.setItem(row, 3, item_cat)

            # 4: Doc date
            if self.target_type == "ΕΞΕΡΧΟΜΕΝΑ":
                doc_d = database.db_to_ui_date(r.get("outgoing_date"))
            else:
                doc_d = database.db_to_ui_date(r.get("incoming_date"))
            item_ddate = QTableWidgetItem(doc_d)
            item_ddate.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tableResults.setItem(row, 4, item_ddate)

            # 5: Doc Type
            self.tableResults.setItem(row, 5, QTableWidgetItem(r.get("doc_type") or ""))

            # 6: Entity
            if self.target_type == "ΕΞΕΡΧΟΜΕΝΑ":
                entity = r.get("outgoing_dest") or ""
            else:
                entity = r.get("incoming_origin") or ""
            self.tableResults.setItem(row, 6, QTableWidgetItem(entity))

            # 7: Description
            if self.target_type == "ΕΞΕΡΧΟΜΕΝΑ":
                desc = r.get("outgoing_desc") or ""
            else:
                desc = r.get("incoming_desc") or ""
            self.tableResults.setItem(row, 7, QTableWidgetItem(desc))

            # 8: Completed
            completed = "ΝΑΙ" if r.get("completed") else "ΟΧΙ"
            item_comp = QTableWidgetItem(completed)
            item_comp.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tableResults.setItem(row, 8, item_comp)

        self.lblStatus.setText(
            f"Βρέθηκαν {len(records)} εγγραφές. (Κάντε διπλό κλικ σε μια γραμμή για προβολή στην κεντρική φόρμα)"
        )

    def reset_filters(self):
        today = QDate.currentDate()
        self.dateFrom.setDate(QDate(today.year(), 1, 1))
        self.dateTo.setDate(today)
        self.comboFilterYear.setCurrentIndex(0)
        self.txtFilterEntity.clear()
        self.txtFilterDocType.clear()
        self.txtFilterDesc.clear()
        self.perform_search()

    def on_row_double_clicked(self, row, column):
        self.open_row(row)

    def open_selected(self):
        selected_rows = self.tableResults.selectionModel().selectedRows()
        if selected_rows:
            self.open_row(selected_rows[0].row())
        else:
            QMessageBox.information(self, "Επιλογή", "Παρακαλώ επιλέξτε μια εγγραφή από τον πίνακα.")

    def open_row(self, row):
        if 0 <= row < len(self.results):
            record = self.results[row]
            if self.parent_window:
                year = record.get("year")
                proto_num = record.get("protocol_number")
                self.parent_window.show_specific_protocol(year, proto_num)
                self.accept()

    def export_results(self):
        if not self.results:
            QMessageBox.warning(self, "Προσοχή", "Δεν υπάρχουν αποτελέσματα προς εξαγωγή.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Εξαγωγή Αποτελεσμάτων Αναζήτησης σε CSV",
            f"search_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )
        if file_path:
            try:
                with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "Α/Α Πρωτοκόλλου", "Έτος", "Ημ. Πρωτοκόλλησης", "Κατηγορία",
                        "Ημ. Εισερχομένου", "Είδος Εγγράφου", "Προέλευση", "Περιγραφή Εισερχ.",
                        "Γραφείο", "Διεκπεραιωμένο", "Ημ. Εξερχομένου", "Προορισμός", "Περιγραφή Εξερχ."
                    ])
                    for r in self.results:
                        writer.writerow([
                            r.get("protocol_number"), r.get("year"), r.get("protocol_date"),
                            r.get("doc_class"), r.get("incoming_date"), r.get("doc_type"),
                            r.get("incoming_origin"), r.get("incoming_desc"), r.get("processing_office"),
                            "ΝΑΙ" if r.get("completed") else "ΟΧΙ",
                            r.get("outgoing_date"), r.get("outgoing_dest"), r.get("outgoing_desc")
                        ])
                QMessageBox.information(self, "Εξαγωγή", "Τα αποτελέσματα εξήχθησαν επιτυχώς!")
            except Exception as e:
                QMessageBox.critical(self, "Σφάλμα", f"Αποτυχία εξαγωγής: {e}")
