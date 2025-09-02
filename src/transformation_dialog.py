from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QSpinBox, QLineEdit

class TransformationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Transformation")
        layout = QFormLayout(self)
        self.dx_spin = QSpinBox()
        self.dx_spin.setRange(-10000, 10000)
        self.dy_spin = QSpinBox()
        self.dy_spin.setRange(-10000, 10000)
        layout.addRow("ΔX:", self.dx_spin)
        layout.addRow("ΔY:", self.dy_spin)
        self.desc_edit = QLineEdit()
        layout.addRow("Description:", self.desc_edit)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_values(self):
        return self.dx_spin.value(), self.dy_spin.value(), self.desc_edit.text()