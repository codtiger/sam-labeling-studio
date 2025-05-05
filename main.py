import sys
from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import QApplication, QStyle
from src.ui import MainWindow


from PyQt6.QtGui import QPalette, QColor

def apply_dark_theme(app):
    """Apply a dark theme to the application."""
    dark_palette = QPalette()

    # Set dark background
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))

    # Set base colors
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(66, 66, 66))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))

    # Set text colors
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))

    # Highlight colors
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))

    # Apply the palette
    app.setPalette(dark_palette)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
