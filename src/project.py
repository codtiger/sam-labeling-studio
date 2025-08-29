import os
import yaml
from pathlib import Path
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QSizePolicy,
    QFrame,
    QVBoxLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QFileDialog,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
)
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtCore import Qt

from src.colorpicker import ColorPickerWidget

PROJECTS_DIR = os.path.expanduser("~/.samstudio/projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)


class Project:
    def __init__(self, name, description, thumbnail, location, labels):
        self.name = name
        self.description = description
        self.thumbnail = thumbnail
        self.location = location
        self.labels = labels

    @property
    def yaml_path(self):
        return os.path.join(PROJECTS_DIR, f"{self.name}.yaml")

    def save(self):
        data = {
            "name": self.name,
            "description": self.description,
            "thumbnail": self.thumbnail,
            "location": self.location,
            "labels": self.labels,
        }
        with open(self.yaml_path, "w") as f:
            yaml.safe_dump(data, f)

    @staticmethod
    def load(path):
        with open(path, "r") as f:
            data = yaml.safe_load(f)
            return Project(
                data["name"],
                data.get("description", ""),
                data.get("thumbnail", ""),
                data.get("location", ""),
                data.get("labels", {}),
            )

    @staticmethod
    def load_all():
        projects = []
        for file in Path(PROJECTS_DIR).glob("*.yaml"):
            with open(file, "r") as f:
                data = yaml.safe_load(f)
                projects.append(
                    Project(
                        data["name"],
                        data.get("description", ""),
                        data.get("thumbnail", ""),
                        data.get("location", ""),
                        data.get("labels", {}),
                    )
                )
        return projects


class ProjectCreateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setFixedWidth(200)
        self.desc_edit = QTextEdit()
        self.thumb_label = QLabel("No thumbnail selected")
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_path = ""
        self.loc_edit = QLineEdit()
        self.loc_edit.setFixedWidth(200)
        self.labels = {}

        layout.addWidget(QLabel("Project Name:"))
        layout.addWidget(self.name_edit, alignment=Qt.AlignmentFlag.AlignLeft, stretch=1)
        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self.desc_edit)
        layout.addWidget(QLabel("Project Thumbnail:"))
        layout.addWidget(self.thumb_label)
        thumb_btn = QPushButton("Browse")
        thumb_btn.setMaximumSize(200, 50)
        thumb_btn.clicked.connect(self.choose_thumbnail)
        layout.addWidget(thumb_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(QLabel("Project Location:"))
        layout.addWidget(self.loc_edit, alignment=Qt.AlignmentFlag.AlignLeft, stretch=1)
        loc_btn = QPushButton("Browse")
        loc_btn.clicked.connect(self.choose_location)
        loc_btn.setMaximumSize(200, 50)
        layout.addWidget(loc_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(QLabel("Labels:"))
        self.labels_widget = LabelColorWidget(self)
        layout.addWidget(self.labels_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def choose_thumbnail(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Thumbnail", "", "Images (*.png *.jpg *.jpeg)"
        )
        if path:
            self.thumb_path = path
            pixmap = QPixmap(path).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio)
            self.thumb_label.setPixmap(pixmap)

    def choose_location(self):
        path = QFileDialog.getExistingDirectory(self, "Select Project Location")
        if path:
            self.loc_edit.setText(path)

    def get_project(self):
        return Project(
            self.name_edit.text().strip(),
            self.desc_edit.toPlainText().strip(),
            self.thumb_path,
            self.loc_edit.text().strip(),
            self.labels,
        )


class LabelEditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Label")
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)
        self._color_picker = ColorPickerWidget(None)

        form_layout = QHBoxLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Label name")

        self.color_edit = QLineEdit()
        self.color_edit.setPlaceholderText("#ffffff")

        self.color_bttn = QPushButton("")
        self.color_bttn.setStyleSheet("background-color: blue;")
        self.color_bttn.clicked.connect(self.show_color_picker)
        self.color_bttn.mouse

        form_layout.addWidget(QLabel("Label:"))
        form_layout.addWidget(self.name_edit)
        form_layout.addWidget(self.color_edit)
        form_layout.addWidget(self.color_bttn)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def show_color_picker(self, event):
        self._color_picker.setWindowFlag(Qt.WindowType.Popup)
        point = self.cursor().pos()
        if point.y() - 200 > 0:
            self._color_picker.move(point.x(), point.y() - 200)
        else:
            self._color_picker.move(point.x(), 0)
        self._color_picker.show()

    def get_label(self):
        name = self.name_edit.text().strip()
        color = self.color_picker.currentColor()
        if not name or not color.isValid():
            return None, None
        rgb = (color.red(), color.green(), color.blue())
        return name, rgb


class LabelColorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(350)
        main_layout = QVBoxLayout(self)

        # Top row: + and - buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+")
        self.add_btn.setFixedWidth(30)
        self.add_btn.setToolTip("Add Label")
        self.remove_btn = QPushButton("-")
        self.remove_btn.setFixedWidth(30)
        self.remove_btn.setToolTip("Remove Selected Label")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # List of labels
        self.label_list = QListWidget()
        main_layout.addWidget(self.label_list)

        # Dialog buttons
        # self.button_box = QDialogButtonBox(
        #     QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        # )
        # main_layout.addWidget(self.button_box)

        # Connections
        self.add_btn.clicked.connect(self.add_label_dialog)
        self.remove_btn.clicked.connect(self.remove_selected_label)

        self.labels = {}

    def add_label_dialog(self):
        dlg = LabelEditDialog()
        if dlg.exec():
            name, rgb = dlg.get_label()
            if name and rgb:
                self.labels[name] = rgb
                item = QListWidgetItem(name)
                item.setBackground(QColor(*rgb))
                item.setData(Qt.ItemDataRole.UserRole, (name, rgb))
                self.label_list.addItem(item)

    def remove_selected_label(self):
        row = self.label_list.currentRow()
        if row >= 0:
            item = self.label_list.takeItem(row)
            if item:
                name, _ = item.data(Qt.ItemDataRole.UserRole)
                if name in self.labels:
                    del self.labels[name]

    def get_label(self):
        return self.labels


class StartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Project")
        self.setMinimumWidth(700)
        self.setMinimumHeight(700)
        main_layout = QGridLayout(self)
        self.left_panel = QVBoxLayout()
        self.left_panel.setObjectName("left_panel")
        self.left_panel.setAlignment(Qt.AlignmentFlag.AlignTop)

        logo_widget = QSvgWidget(self)
        logo_widget.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        logo_widget.load(os.path.join("assets", "samstudio.svg"))
        logo_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        logo_widget.setMinimumSize(100, 100)
        logo_widget.setMaximumSize(200, 200)

        self.button_grp = QButtonGroup(self)

        new_project_bttn = QPushButton("Create New Project")
        new_project_bttn.setStyleSheet(
            "QPushButton {border: none; background-color: transparent; color: #2f67f5;}"
            "QPushButton:hover { text-decoration: underline; font-weight: bold; }"
        )
        open_project_bttn = QPushButton("Open Project File")
        open_project_bttn.setStyleSheet(
            "QPushButton {border: none; background-color: transparent; color: #2f67f5;}"
            "QPushButton:hover { text-decoration: underline; font-weight: bold; }"
        )
        open_editor_bttn = QPushButton("New Window")
        open_editor_bttn.setStyleSheet(
            "QPushButton {border: none; background-color: transparent; color: #2f67f5;}"
            "QPushButton:hover { text-decoration: underline; font-weight: bold; }"
        )
        

        self.button_grp.addButton(new_project_bttn)
        self.button_grp.addButton(open_project_bttn)
        self.button_grp.addButton(open_editor_bttn)

        new_project_bttn.clicked.connect(self.show_create_dialog)
        open_project_bttn.clicked.connect(self.show_project_select_dialog)
        open_editor_bttn.clicked.connect(self.open_editor)


        self.left_panel.addWidget(logo_widget)
        self.left_panel.addWidget(new_project_bttn)
        self.left_panel.addWidget(open_project_bttn)
        self.left_panel.addWidget(open_editor_bttn)

        main_layout.addLayout(self.left_panel, 0, 0, 1, 1)

        left_panel = QVBoxLayout()
        left_panel.setObjectName("project_select_panel")
        recents_label = QLabel("Recent Projects:")
        recents_label.setStyleSheet("QLabel {font-weight: bold; font-size: 1.5em; color: #2f67f5;}")

        self.project_list = QListWidget()
        self.project_list.setStyleSheet(
            "QListWidget {background-color: transparent; color: #2f67f5;}"
        )
        self.projects = Project.load_all()
        for proj in self.projects:
            item = QListWidgetItem(f"{proj.name}\n{proj.description}")
            if proj.thumbnail and os.path.exists(proj.thumbnail):
                pixmap = QPixmap(proj.thumbnail).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio)
                item.setIcon(pixmap)
            item.setData(Qt.ItemDataRole.UserRole, proj)
            self.project_list.addItem(item)
        left_panel.addWidget(recents_label)
        left_panel.addWidget(self.project_list)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        separator.setLineWidth(1)
        separator.setStyleSheet("color: #828181;")

        main_layout.addWidget(separator, 0, 2, 0, 1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        left_panel.addWidget(btns)
        main_layout.addLayout(left_panel, 0, 3, 2, 2)

    def get_selected_project(self):
        item = self.project_list.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        self.close()
        return None

    def show_create_dialog(self, event):
        dlg = ProjectCreateDialog(self)
        if dlg.show():
            proj = dlg.get_project()
            proj.save()
            return proj
        return None

    def open_editor(self, event):
        self.close()
        return None
    def show_project_select_dialog(self, event):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Thumbnail", "", "Yaml files (*.yaml *.yml)"
        )
        if path:
            proj = Project.load(path)
            return proj
        return None
