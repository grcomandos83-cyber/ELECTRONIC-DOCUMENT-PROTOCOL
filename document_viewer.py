"""
document_viewer.py - Εσωτερικός Προβολέας Εγγράφων & PDF (Native Qt Viewer)
───────────────────────────────────────────────────────────────────────────
Υποστηρίζει:
- PDF αρχεία μέσω PyQt6.QtPdf / QPdfView με πολλαπλές σελίδες, ζουμ, περιήγηση
- Εικόνες (JPG, PNG, BMP) με ζουμ, περιστροφή και προσαρμογή
- Εκτύπωση εγγράφων μέσω QPrintDialog / QPrinter
- Εναλλακτικό άνοιγμα με εξωτερικό πρόγραμμα συστήματος
"""

import os
import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QToolBar, QWidget, QScrollArea, QMessageBox,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, QPointF, QEvent
from PyQt6.QtGui import QIcon, QPixmap, QImage, QTransform, QPainter, QKeySequence, QShortcut
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPdfWidgets import QPdfView
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog


class DocumentViewerDialog(QDialog):
    def __init__(self, file_path: str, parent=None, app_icon: QIcon = None):
        super().__init__(parent)
        self.file_path = os.path.abspath(file_path) if file_path else ""
        self.ext = os.path.splitext(self.file_path)[1].lower() if self.file_path else ""
        
        # Εικόνες state
        self.image_pixmap = None
        self.image_scale = 1.0
        self.image_rotation = 0

        # UI Initialization
        self.init_ui(app_icon)
        self.load_document()

    def init_ui(self, app_icon: QIcon = None):
        filename = os.path.basename(self.file_path) if self.file_path else "Έγγραφο"
        self.setWindowTitle(f"Προβολή Εγγράφου: {filename}")
        if app_icon:
            self.setWindowIcon(app_icon)
        self.resize(1050, 850)
        self.setMinimumSize(750, 550)

        # Ενεργοποίηση κουμπιών μεγιστοποίησης και ελαχιστοποίησης στο παράθυρο
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Toolbar / Header Bar ──
        self.toolbar_widget = QWidget(self)
        self.toolbar_widget.setStyleSheet("""
            QWidget {
                background-color: #1e293b;
                color: #f8fafc;
                font-family: 'Segoe UI', Tahoma, sans-serif;
            }
            QPushButton {
                background-color: #334155;
                color: #f8fafc;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: bold;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #475569;
                border-color: #64748b;
            }
            QPushButton:pressed {
                background-color: #0ea5e9;
                border-color: #0284c7;
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #64748b;
                border-color: #334155;
            }
            QLineEdit {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 2px 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QLabel {
                font-size: 12px;
                font-weight: bold;
            }
        """)

        tb_layout = QHBoxLayout(self.toolbar_widget)
        tb_layout.setContentsMargins(12, 8, 12, 8)
        tb_layout.setSpacing(8)

        # 1. Page Navigation (για PDF)
        self.btn_prev = QPushButton("◀ Πίσω", self.toolbar_widget)
        self.btn_prev.setToolTip("Προηγούμενη σελίδα (PageUp ή ◀)")
        self.btn_prev.clicked.connect(self.prev_page)

        self.txt_page = QLineEdit(self.toolbar_widget)
        self.txt_page.setFixedWidth(40)
        self.txt_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.txt_page.returnPressed.connect(self.on_jump_page)

        self.lbl_page_total = QLabel(" / 1", self.toolbar_widget)
        self.lbl_page_total.setStyleSheet("color: #94a3b8;")

        self.btn_next = QPushButton("Μπροστά ▶", self.toolbar_widget)
        self.btn_next.setToolTip("Επόμενη σελίδα (PageDown ή ▶)")
        self.btn_next.clicked.connect(self.next_page)

        tb_layout.addWidget(self.btn_prev)
        tb_layout.addWidget(self.txt_page)
        tb_layout.addWidget(self.lbl_page_total)
        tb_layout.addWidget(self.btn_next)

        # Separator
        sep1 = QFrame(self.toolbar_widget)
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("color: #475569;")
        tb_layout.addWidget(sep1)

        # 2. Zoom Controls
        self.btn_zoom_out = QPushButton("🔍 -", self.toolbar_widget)
        self.btn_zoom_out.setToolTip("Σμίκρυνση (Ctrl+-)")
        self.btn_zoom_out.clicked.connect(self.zoom_out)

        self.lbl_zoom = QLabel("100%", self.toolbar_widget)
        self.lbl_zoom.setFixedWidth(50)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_zoom.setStyleSheet("color: #38bdf8; font-weight: bold;")

        self.btn_zoom_in = QPushButton("🔍 +", self.toolbar_widget)
        self.btn_zoom_in.setToolTip("Μεγέθυνση (Ctrl++)")
        self.btn_zoom_in.clicked.connect(self.zoom_in)

        self.btn_fit_width = QPushButton("↔ Πλάτος", self.toolbar_widget)
        self.btn_fit_width.setToolTip("Προσαρμογή στο πλάτος παραθύρου")
        self.btn_fit_width.clicked.connect(self.fit_width)

        self.btn_fit_page = QPushButton("📄 Σελίδα", self.toolbar_widget)
        self.btn_fit_page.setToolTip("Προσαρμογή ολόκληρης σελίδας")
        self.btn_fit_page.clicked.connect(self.fit_page)

        tb_layout.addWidget(self.btn_zoom_out)
        tb_layout.addWidget(self.lbl_zoom)
        tb_layout.addWidget(self.btn_zoom_in)
        tb_layout.addWidget(self.btn_fit_width)
        tb_layout.addWidget(self.btn_fit_page)

        # 3. Rotate (για εικόνες)
        self.btn_rotate = QPushButton("🔄 Περιστροφή", self.toolbar_widget)
        self.btn_rotate.setToolTip("Περιστροφή κατά 90° δεξιόστροφα")
        self.btn_rotate.clicked.connect(self.rotate_image)
        tb_layout.addWidget(self.btn_rotate)

        # Spacer
        tb_layout.addStretch()

        # 4. Action Buttons
        self.btn_print = QPushButton("🖨️ Εκτύπωση", self.toolbar_widget)
        self.btn_print.setToolTip("Εκτύπωση εγγράφου (Ctrl+P)")
        self.btn_print.setStyleSheet("background-color: #0369a1; border-color: #0284c7;")
        self.btn_print.clicked.connect(self.print_document)

        self.btn_external = QPushButton("↗️ Εξωτερικό", self.toolbar_widget)
        self.btn_external.setToolTip("Άνοιγμα με την προεπιλεγμένη εφαρμογή του συστήματος")
        self.btn_external.clicked.connect(self.open_external)

        self.btn_maximize = QPushButton("🗖", self.toolbar_widget)
        self.btn_maximize.setToolTip("Μεγιστοποίηση / Επαναφορά παραθύρου (F11)")
        self.btn_maximize.setStyleSheet("background-color: #334155; border-color: #475569; font-weight: bold; width: 22px;")
        self.btn_maximize.clicked.connect(self.toggle_maximize)

        self.btn_close = QPushButton("✕", self.toolbar_widget)
        self.btn_close.setToolTip("Κλείσιμο προβολέα (Esc)")
        self.btn_close.setStyleSheet("background-color: #e11d48; border-color: #be123c; font-weight: bold; width: 20px;")
        self.btn_close.clicked.connect(self.close)

        tb_layout.addWidget(self.btn_print)
        tb_layout.addWidget(self.btn_external)
        tb_layout.addWidget(self.btn_maximize)
        tb_layout.addWidget(self.btn_close)

        main_layout.addWidget(self.toolbar_widget)

        # ── Central Content Area ──
        self.content_container = QWidget(self)
        self.content_container.setStyleSheet("background-color: #525659;")
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        # PDF View Widget
        self.pdf_document = QPdfDocument(self)
        self.pdf_view = QPdfView(self.content_container)
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.pdf_view.pageNavigator().currentPageChanged.connect(self.on_pdf_page_changed)
        self.content_layout.addWidget(self.pdf_view)

        # Image ScrollArea Widget
        self.image_scroll = QScrollArea(self.content_container)
        self.image_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_scroll.setStyleSheet("background-color: #334155; border: none;")
        self.lbl_image = QLabel(self.image_scroll)
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_scroll.setWidget(self.lbl_image)
        self.content_layout.addWidget(self.image_scroll)

        # Generic File Card Widget (για αρχεία Word, Excel κ.λπ.)
        self.card_widget = QWidget(self.content_container)
        card_layout = QVBoxLayout(self.card_widget)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_card_title = QLabel(self.card_widget)
        self.lbl_card_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white; margin-bottom: 12px;")
        self.btn_card_open = QPushButton("Άνοιγμα με την Προεπιλεγμένη Εφαρμογή", self.card_widget)
        self.btn_card_open.setStyleSheet("background-color: #0284c7; color: white; padding: 10px 20px; font-size: 14px; font-weight: bold; border-radius: 6px;")
        self.btn_card_open.clicked.connect(self.open_external)
        card_layout.addWidget(self.lbl_card_title, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.btn_card_open, alignment=Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.card_widget)

        main_layout.addWidget(self.content_container)

        # Keyboard Shortcuts
        QShortcut(QKeySequence("Esc"), self, self.close)
        QShortcut(QKeySequence("+"), self, self.zoom_in)
        QShortcut(QKeySequence("="), self, self.zoom_in)
        QShortcut(QKeySequence("-"), self, self.zoom_out)
        QShortcut(QKeySequence("Ctrl+P"), self, self.print_document)
        QShortcut(QKeySequence("F11"), self, self.toggle_maximize)
        QShortcut(QKeySequence(Qt.Key.Key_PageUp), self, self.prev_page)
        QShortcut(QKeySequence(Qt.Key.Key_PageDown), self, self.next_page)

    # ── Φόρτωση Εγγράφου ──
    def load_document(self):
        if not self.file_path or not os.path.exists(self.file_path):
            QMessageBox.warning(self, "Σφάλμα", "Το αρχείο δεν υπάρχει ή η διαδρομή είναι άκυρη.")
            self.close()
            return

        if self.ext == ".pdf":
            self.setup_pdf_mode()
        elif self.ext in (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"):
            self.setup_image_mode()
        else:
            self.setup_generic_mode()

    def setup_pdf_mode(self):
        self.pdf_view.show()
        self.image_scroll.hide()
        self.card_widget.hide()
        self.btn_rotate.hide()

        self.btn_prev.show()
        self.txt_page.show()
        self.lbl_page_total.show()
        self.btn_next.show()
        self.btn_fit_width.show()
        self.btn_fit_page.show()

        try:
            self.pdf_document.load(self.file_path)
            total_pages = self.pdf_document.pageCount()
            self.lbl_page_total.setText(f" / {max(1, total_pages)}")
            self.txt_page.setText("1")
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self.update_zoom_label(self.pdf_view.zoomFactor())
        except Exception as e:
            QMessageBox.critical(self, "Σφάλμα PDF", f"Αποτυχία φόρτωσης αρχείου PDF:\n{e}")

    def setup_image_mode(self):
        self.pdf_view.hide()
        self.image_scroll.show()
        self.card_widget.hide()

        self.btn_prev.hide()
        self.txt_page.hide()
        self.lbl_page_total.hide()
        self.btn_next.hide()
        self.btn_rotate.show()
        self.btn_fit_width.setText("↔ Προσαρμογή")
        self.btn_fit_page.hide()

        self.image_pixmap = QPixmap(self.file_path)
        self.image_scale = 1.0
        self.image_rotation = 0
        self.render_image()

    def setup_generic_mode(self):
        self.pdf_view.hide()
        self.image_scroll.hide()
        self.card_widget.show()

        self.btn_prev.hide()
        self.txt_page.hide()
        self.lbl_page_total.hide()
        self.btn_next.hide()
        self.btn_rotate.hide()
        self.btn_zoom_in.hide()
        self.btn_zoom_out.hide()
        self.lbl_zoom.hide()
        self.btn_fit_width.hide()
        self.btn_fit_page.hide()
        self.btn_print.hide()

        filename = os.path.basename(self.file_path)
        self.lbl_card_title.setText(f"📄 Αρχείο: {filename}\n(Δεν υποστηρίζεται άμεση ενσωματωμένη προεπισκόπηση για τύπο {self.ext.upper()})")

    # ── PDF Event Handlers ──
    def on_pdf_page_changed(self, page_index: int):
        self.txt_page.setText(str(page_index + 1))
        total = self.pdf_document.pageCount()
        self.btn_prev.setEnabled(page_index > 0)
        self.btn_next.setEnabled(page_index < total - 1)

    def prev_page(self):
        if self.ext == ".pdf":
            nav = self.pdf_view.pageNavigator()
            cur = nav.currentPage()
            if cur > 0:
                nav.jump(cur - 1, QPointF(), 0)

    def next_page(self):
        if self.ext == ".pdf":
            nav = self.pdf_view.pageNavigator()
            cur = nav.currentPage()
            total = self.pdf_document.pageCount()
            if cur < total - 1:
                nav.jump(cur + 1, QPointF(), 0)

    def on_jump_page(self):
        if self.ext == ".pdf":
            try:
                page_num = int(self.txt_page.text().strip())
                total = self.pdf_document.pageCount()
                if 1 <= page_num <= total:
                    self.pdf_view.pageNavigator().jump(page_num - 1, QPointF(), 0)
                else:
                    self.txt_page.setText(str(self.pdf_view.pageNavigator().currentPage() + 1))
            except ValueError:
                self.txt_page.setText(str(self.pdf_view.pageNavigator().currentPage() + 1))

    # ── Zoom Handlers ──
    def zoom_in(self):
        if self.ext == ".pdf":
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
            new_factor = min(4.0, self.pdf_view.zoomFactor() * 1.25)
            self.pdf_view.setZoomFactor(new_factor)
            self.update_zoom_label(new_factor)
        elif self.image_pixmap:
            self.image_scale = min(4.0, self.image_scale * 1.25)
            self.render_image()

    def zoom_out(self):
        if self.ext == ".pdf":
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
            new_factor = max(0.25, self.pdf_view.zoomFactor() / 1.25)
            self.pdf_view.setZoomFactor(new_factor)
            self.update_zoom_label(new_factor)
        elif self.image_pixmap:
            self.image_scale = max(0.2, self.image_scale / 1.25)
            self.render_image()

    def fit_width(self):
        if self.ext == ".pdf":
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self.update_zoom_label(self.pdf_view.zoomFactor())
        elif self.image_pixmap:
            container_w = self.image_scroll.viewport().width() - 40
            orig_w = self.image_pixmap.width()
            if orig_w > 0:
                self.image_scale = max(0.2, container_w / orig_w)
                self.render_image()

    def fit_page(self):
        if self.ext == ".pdf":
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
            self.update_zoom_label(self.pdf_view.zoomFactor())

    def update_zoom_label(self, factor: float):
        percent = int(factor * 100)
        self.lbl_zoom.setText(f"{percent}%")

    # ── Image Specific Handlers ──
    def rotate_image(self):
        if self.image_pixmap:
            self.image_rotation = (self.image_rotation + 90) % 360
            self.render_image()

    def render_image(self):
        if not self.image_pixmap or self.image_pixmap.isNull():
            return

        pix = self.image_pixmap
        if self.image_rotation != 0:
            transform = QTransform().rotate(self.image_rotation)
            pix = pix.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        target_w = max(10, int(pix.width() * self.image_scale))
        target_h = max(10, int(pix.height() * self.image_scale))
        scaled_pix = pix.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.lbl_image.setPixmap(scaled_pix)
        self.lbl_image.adjustSize()
        self.update_zoom_label(self.image_scale)

    # ── Actions: Print & External ──
    def print_document(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Εκτύπωση Εγγράφου")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        painter = QPainter(printer)
        try:
            if self.ext == ".pdf":
                total = self.pdf_document.pageCount()
                for p in range(total):
                    if p > 0:
                        printer.newPage()
                    page_size = self.pdf_document.pagePointSize(p).toSize()
                    # Render page at 2x for sharp print quality
                    img = self.pdf_document.render(p, page_size * 2)
                    rect = painter.viewport()
                    scaled = img.scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    painter.drawImage(0, 0, scaled)
            elif self.image_pixmap:
                rect = painter.viewport()
                scaled = self.image_pixmap.scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                painter.drawImage(0, 0, scaled)
        except Exception as e:
            QMessageBox.critical(self, "Σφάλμα Εκτύπωσης", f"Αποτυχία εκτύπωσης: {e}")
        finally:
            painter.end()

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.btn_maximize.setText("🗖")
            self.btn_maximize.setToolTip("Μεγιστοποίηση παραθύρου (F11)")
        else:
            self.showMaximized()
            self.btn_maximize.setText("🗗")
            self.btn_maximize.setToolTip("Επαναφορά μεγέθους παραθύρου (F11)")

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if hasattr(self, 'btn_maximize'):
                if self.isMaximized():
                    self.btn_maximize.setText("🗗")
                    self.btn_maximize.setToolTip("Επαναφορά μεγέθους παραθύρου (F11)")
                else:
                    self.btn_maximize.setText("🗖")
                    self.btn_maximize.setToolTip("Μεγιστοποίηση παραθύρου (F11)")
        super().changeEvent(event)

    def closeEvent(self, event):
        try:
            if hasattr(self, 'pdf_document'):
                self.pdf_document.close()
        except Exception:
            pass
        super().closeEvent(event)

    def open_external(self):
        if self.file_path and os.path.exists(self.file_path):
            os.startfile(self.file_path)
