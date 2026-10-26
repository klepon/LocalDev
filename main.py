import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow

# PyInstaller unpacks bundled files into sys._MEIPASS.
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

STYLE = """
QLabel#title { font-size: 18px; font-weight: 600; }
QLabel#heading { font-weight: 600; }
QLabel#muted { color: gray; }
QLabel#error { color: #dc2626; }
QPushButton { padding: 5px 12px; }
QPushButton#primary { background: #2563eb; color: white; border: none; border-radius: 4px; font-weight: 600; }
QPushButton#primary:disabled { background: #93a3b8; }
QPushButton#danger { color: #dc2626; }
QGroupBox { font-weight: 600; }
"""


def main():
    # Own taskbar identity, so the taskbar shows LocalDev's icon instead of python's.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LocalDev")
    app = QApplication(sys.argv)
    app.setApplicationName("LocalDev")
    app.setWindowIcon(QIcon(str(BASE / "assets" / "icon.ico")))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
