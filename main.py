"""
Ηλεκτρονικό Πρωτόκολλο Εγγράφων — Κύριο Σημείο Εκκίνησης (Application Entry Point)
"""

import sys
import ctypes

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from app.config import (
    setup_environment, get_app_icon_path, APP_USER_MODEL_ID
)
from app.ui import ProtocolMainWindow

# Κλείδωμα Τρέχοντος Καταλόγου Εργασίας για αποφυγή σφαλμάτων διαδρομών
setup_environment()


def main():
    # Set Windows AppUserModelID so taskbar groups properly and displays the custom app icon
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
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
