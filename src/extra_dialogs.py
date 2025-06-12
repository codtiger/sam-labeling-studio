from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
)


class PreferencesDialog(QDialog):
    def __init__(self, parent=None, defaults: dict = {}):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        layout = QFormLayout(self)

        # Host and port
        self.host_input = QLineEdit(defaults.get("host", "localhost"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(defaults.get("port", 8000))

        # Inference settings
        self.k_input = QSpinBox()
        self.k_input.setRange(1, 100)
        self.k_input.setValue(defaults.get("k", 5))

        self.conf_thresh_input = QDoubleSpinBox()
        self.conf_thresh_input.setRange(0.0, 1.0)
        self.conf_thresh_input.setSingleStep(0.01)
        self.conf_thresh_input.setValue(defaults.get("confidence_threshold", 0.5))

        self.nms_thresh_input = QDoubleSpinBox()
        self.nms_thresh_input.setRange(0.0, 1.0)
        self.nms_thresh_input.setSingleStep(0.01)
        self.nms_thresh_input.setValue(defaults.get("nms_threshold", 0.5))

        self.num_points_input = QSpinBox()
        self.num_points_input.setRange(1, 1000)
        self.num_points_input.setValue(defaults.get("num_points", 10))

        layout.addRow("Host:", self.host_input)
        layout.addRow("Port:", self.port_input)
        layout.addRow("k:", self.k_input)
        layout.addRow("Confidence Threshold:", self.conf_thresh_input)
        layout.addRow("NMS Threshold:", self.nms_thresh_input)
        layout.addRow("Number of Points:", self.num_points_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "host": self.host_input.text(),
            "port": self.port_input.value(),
            "k": self.k_input.value(),
            "confidence_threshold": self.conf_thresh_input.value(),
            "nms_threshold": self.nms_thresh_input.value(),
            "num_points": self.num_points_input.value(),
        }
