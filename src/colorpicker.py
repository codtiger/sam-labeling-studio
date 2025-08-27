from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QMouseEvent, QPixmap, QFont
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal

class ColorPickerWidget(QWidget):
    colorChanged = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 200)
        self.hue = 0  # 0-359
        self.sat = 1.0  # 0-1
        self.val = 1.0  # 0-1
        self.alpha = 1.0  # 0-1

        self.margin = 16
        self.square_size = 180
        self.bar_width = 24
        self.bar_height = self.square_size
        self.preview_height = 32

        self.selected_area = 'sv'  # 'sv', 'hue', 'alpha'
        self.setMouseTracking(True)

        self._sv_pixmap = None
        self._sv_hue = None

    def getColor(self):
        color = QColor.fromHsvF(self.hue / 359.0, self.sat, self.val, self.alpha)
        return color
    
    def paintEvent(self, event):
        painter = QPainter(self)
        # preview bar
        color = self.getColor()
        preview_rect = QRect(0, 0, 300, self.preview_height)
        painter.fillRect(preview_rect, color)
        painter.setPen(Qt.GlobalColor.black if color.lightnessF() > 0.5 else Qt.GlobalColor.white)
        hex_str = color.name(QColor.NameFormat.HexArgb)

        painter.drawText(preview_rect, Qt.AlignmentFlag.AlignCenter, hex_str)

        # SV (saturation-value) square
        sv_rect = QRect(self.margin, self.preview_height + self.margin, self.square_size, self.square_size)
        self.drawSVRect(painter, sv_rect)

        # hue bar
        hue_rect = QRect(self.margin + self.square_size + self.margin, self.preview_height + self.margin, self.bar_width, self.bar_height)
        self.drawHueBar(painter, hue_rect)

        # alpha bar
        alpha_rect = QRect(self.margin + self.square_size + 2 * self.margin + self.bar_width, self.preview_height + self.margin, self.bar_width, self.bar_height)
        self.drawAlphaBar(painter, alpha_rect)

        # Selectors
        # SV selector
        sv_x = sv_rect.left() + int(self.sat * (sv_rect.width() - 1))
        sv_y = sv_rect.top() + int((1 - self.val) * (sv_rect.height() - 1))
        painter.setPen(Qt.GlobalColor.black)
        painter.drawEllipse(QPoint(sv_x, sv_y), 6, 6)

        # Hue selector
        hue_y = hue_rect.top() + int((1 - self.hue / 359.0) * (hue_rect.height() - 1))
        painter.setPen(Qt.GlobalColor.white)
        painter.drawRect(hue_rect.left() - 2, hue_y - 2, hue_rect.width() + 4, 4)

        # Alpha selector
        alpha_y = alpha_rect.top() + int((1 - self.alpha) * (alpha_rect.height() - 1))
        painter.setPen(Qt.GlobalColor.black)
        painter.drawRect(alpha_rect.left() - 2, alpha_y - 2, alpha_rect.width() + 4, 4)

    def drawSVRect(self, painter: QPainter, rect: QRect):
        # Horizontal: saturation (left=0, right=1)
        # Vertical: value (top=1, bottom=0)
        if self._sv_pixmap is None or self._sv_hue != self.hue:
            self._sv_pixmap = QPixmap(rect.size())
            self._sv_pixmap.fill(Qt.GlobalColor.transparent)
            p = QPainter(self._sv_pixmap)

            for x in range(rect.width()):
                s = x / (rect.width() - 1)
                for y in range(rect.height()):
                    v = 1 - y / (rect.height() - 1)
                    color = QColor.fromHsvF(self.hue / 359.0, s, v, 1.0)
                    p.setPen(color)
                    p.drawPoint(x, y)
            p.end()
            self._sv_hue_ = self.hue
        painter.drawPixmap(rect, self._sv_pixmap)

    def drawHueBar(self, painter, rect):
        for y in range(rect.height()):
            h = (1 - y / (rect.height() - 1)) * 359
            color = QColor.fromHsvF(h / 359.0, 1, 1, 1)
            painter.setPen(color)
            painter.drawLine(rect.left(), rect.top() + y, rect.right(), rect.top() + y)

    def drawAlphaBar(self, painter, rect):
        # Draw checkerboard background
        checker_size = 6
        for y in range(rect.top(), rect.bottom(), checker_size):
            for x in range(rect.left(), rect.right(), checker_size):
                if ((x // checker_size) + (y // checker_size)) % 2 == 0:
                    painter.fillRect(QRect(x, y, checker_size, checker_size), Qt.GlobalColor.lightGray)
                else:
                    painter.fillRect(QRect(x, y, checker_size, checker_size), Qt.GlobalColor.white)
        # Draw alpha gradient
        for y in range(rect.height()):
            a = 1 - y / (rect.height() - 1)
            color = QColor.fromHsvF(self.hue / 359.0, self.sat, self.val, a)
            painter.setPen(color)
            painter.drawLine(rect.left(), rect.top() + y, rect.right(), rect.top() + y)

    def mousePressEvent(self, event: QMouseEvent):
        self.handleMouse(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.handleMouse(event)

    def handleMouse(self, event: QMouseEvent):
        x, y = event.position().toPoint().x(), event.position().toPoint().y()
        sv_rect = QRect(self.margin, self.preview_height + self.margin, self.square_size, self.square_size)
        hue_rect = QRect(self.margin + self.square_size + self.margin, self.preview_height + self.margin, self.bar_width, self.bar_height)
        alpha_rect = QRect(self.margin + self.square_size + 2 * self.margin + self.bar_width, self.preview_height + self.margin, self.bar_width, self.bar_height)

        if sv_rect.contains(x, y):
            self.selected_area = 'sv'
            self.sat = min(max((x - sv_rect.left()) / (sv_rect.width() - 1), 0), 1)
            self.val = 1 - min(max((y - sv_rect.top()) / (sv_rect.height() - 1), 0), 1)
            self.colorChanged.emit(self.getColor())
            self.update()
        elif hue_rect.contains(x, y):
            self.selected_area = 'hue'
            self.hue = min(max(359 * (1 - (y - hue_rect.top()) / (hue_rect.height() - 1)), 0), 359)
            self.colorChanged.emit(self.getColor())
            self.update()
        elif alpha_rect.contains(x, y):
            self.selected_area = 'alpha'
            self.alpha = min(max(1 - (y - alpha_rect.top()) / (alpha_rect.height() - 1), 0), 1)
            self.colorChanged.emit(self.getColor())
            self.update()

    def setColor(self, color: QColor):
        h, s, v, a = color.getHsvF()
        self.hue = int(h * 359)
        self.sat = s
        self.val = v
        self.alpha = a
        self.update()

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        return self.size()