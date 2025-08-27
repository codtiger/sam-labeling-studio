import sys
import os
import argparse
import yaml

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QStyle, QDialog
from PyQt6.QtGui import QPalette, QColor

from src.ui import MainWindow
from src.startup import get_or_create_project
from src.project import Project, StartupDialog


def apply_dark_theme(app):
    """Apply a dark theme to the application."""
    dark_palette = QPalette()

    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))

    dark_palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(66, 66, 66))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(10, 10, 10))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))

    dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))

    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))

    # Apply the palette
    app.setPalette(dark_palette)


def change_title():
    if sys.platform.startswith("darwin"):
        # Set app name, if PyObjC is installed
        # Python 2 has PyObjC preinstalled
        # Python 3: pip3 install pyobjc-framework-Cocoa
        try:
            from Foundation import NSBundle

            bundle = NSBundle.mainBundle()
            if bundle:
                app_info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                if app_info:
                    app_info["CFBundleName"] = "Sam Studio"
        except ImportError:
            pass

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Sam Labeling Studio")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/app_config.yaml",
        help="Path to the configuration file",
    )
    parser.add_argument("--use-native-file-dialog", action="store_true", help="Use native file dialog",default=False)
    return parser.parse_args()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Sam Labeling Studio")
    icon = QIcon("assets/samstudio_logo_only.svg")
    app.setWindowIcon(icon)
    args = vars(parse_args())
    project = get_or_create_project(icon=icon)
    if not project:
        sys.exit(0)

    apply_dark_theme(app)
    window = MainWindow(arguments=args)
    window.setWindowTitle("Sam Labeling Studio")
    window.show()
    change_title()
    sys.exit(app.exec())
