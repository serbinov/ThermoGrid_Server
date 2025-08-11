# file: main.py
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt # <-- ИСПРАВЛЕНИЕ: Добавлен этот импорт

from main_window import MainWindow
from database import initialize_db
from config import APP_NAME

if __name__ == "__main__":
    QApplication.setOrganizationName("MyCompany")
    QApplication.setApplicationName(APP_NAME)
    
    initialize_db()
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    
    # Настройка темной палитры
    dark_palette = app.palette() 
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(dark_palette)
    
    app.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }")
    
    window = MainWindow()
    sys.exit(app.exec())