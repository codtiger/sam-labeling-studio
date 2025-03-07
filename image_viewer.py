from typing import override
from PyQt6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsEllipseItem,
    QGraphicsItem,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QEvent
from PyQt6.QtGui import QPixmap, QBrush, QColor, QPolygonF, QPen, QPainter


class VertexItem(QGraphicsEllipseItem):
    """Custom item for polygon vertices that updates the parent polygon when moved."""

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.data(
            0
        ):
            new_pos = value
            polygon_item = self.data(0)
            index = self.data(1)
            poly = polygon_item.polygon()
            # poly[index] = value
            poly[index] = (
                new_pos
                + new_pos
                + QPointF(self.rect().width() / 2, self.rect().height() / 2)
            )
            polygon_item.setPolygon(poly)
            return new_pos
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        print("pressed")
        return super().mousePressEvent(event)


class ImageViewer(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.image_scene = QGraphicsScene()
        self.setScene(self.image_scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.image_item = None  # QGraphicsPixmapItem for the image
        self.points = []  # List of QPointF for point annotations
        self.boxes = []  # List of [start, end] QPointF pairs for box annotations
        self.current_box = None  # Temporary box during drawing
        self.polygon_items = []  # List of QGraphicsPolygonItem for model results
        # self.mode = "Points"  # Current interaction mode: "point" or "box"

        self.temp_points = []  # Temporary points for current polygon
        self.temp_lines = []  # Temporary lines connecting points
        self.temp_polygon = None  # Temporary shaded polygon during drawing
        self.mode = "model"
        self.current_shape = None  # Current shape for manual annotation
        self.prompt_mode = "points"

        # Mode selection (could be extended via UI buttons)
        # For simplicity, toggle with right-click in this example
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def set_mode(self, mode):
        """Set the current mode: 'model' or 'manual'."""
        self.mode = mode
        self.clear_temp()  # Clear temporary annotations when switching modes

    def clear_temp(self):
        """Clear temporary drawing data."""
        self.temp_points = []
        for line in self.temp_lines:
            self.image_scene.removeItem(line)
        self.temp_lines = []
        if self.temp_polygon:
            self.image_scene.removeItem(self.temp_polygon)
            self.temp_polygon = None

    def set_image(self, pixmap):
        """Set the image to display and fit it to the view."""
        # Clear any existing content
        self.clear()
        self.image_item = self.image_scene.addPixmap(pixmap)
        self.setSceneRect(self.image_item.boundingRect())
        self.fitInView(self.image_item, Qt.AspectRatioMode.KeepAspectRatio)

    def set_shape(self, shape):
        if self.mode == "manual":
            self.current_shape = shape
            self.clear_temp()

    def clear(self):
        """Clear all annotations and reset the scene."""
        self.image_scene.clear()
        self.image_item = None
        self.points = []
        self.boxes = []
        self.current_box = None
        self.polygon_items = []
        self.temp_points = []
        self.temp_lines = []
        self.temp_ellipses = []
        if self.temp_polygon:
            self.image_scene.removeItem(self.temp_polygon)
            self.temp_polygon = None

    def display_polygons(self, polygons):
        """Display polygons returned by the model with editable vertices."""
        if self.image_item:
            self.image_item.setOpacity(0.5)  # Lower image opacity
        self.polygon_items = []
        for poly in polygons:
            qpoly = QPolygonF([QPointF(x, y) for x, y in poly])
            polygon_item = self.image_scene.addPolygon(
                qpoly,
                pen=QPen(Qt.GlobalColor.red),
                brush=QBrush(QColor(0, 255, 0, 128)),
            )
            self.polygon_items.append(polygon_item)
            # Add movable vertices
            for i, point in enumerate(qpoly):
                vertex_item = VertexItem(point.x() - 3, point.y() - 3, 12, 12)
                vertex_item.setBrush(Qt.GlobalColor.blue)
                vertex_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
                vertex_item.setData(0, polygon_item)  # Reference to polygon
                vertex_item.setData(1, i)  # Index in polygon
                self.image_scene.addItem(vertex_item)

    def highlight_polygon(self, index):
        """Highlight the selected polygon."""
        for i, item in enumerate(self.polygon_items):
            if i == index:
                item.setBrush(QBrush(QColor(255, 0, 0, 128)))  # Red for selected
            else:
                item.setBrush(QBrush(QColor(0, 255, 0, 128)))  # Green for others

    def setMousePrompt(self, text):
        self.prompt_mode = text

    def mousePressEvent(self, event):
        """Handle mouse press for point or box annotation."""
        pos = self.mapToScene(event.pos())
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.mode == "manual"
            and self.current_shape != None
        ):
            self.temp_points.append(pos)
            ellipse = self.image_scene.addEllipse(
                pos.x() - 2, pos.y() - 2, 6, 6, brush=Qt.GlobalColor.red
            )
            self.temp_ellipses.append(ellipse)
            if len(self.temp_points) > 1:
                line = self.image_scene.addLine(
                    self.temp_points[-2].x(),
                    self.temp_points[-2].y(),
                    pos.x(),
                    pos.y(),
                    QPen(Qt.GlobalColor.black),
                )
                self.temp_lines.append(line)
        elif self.mode == "box":
            self.current_box = [pos, pos]
        elif event.button() == Qt.MouseButton.RightButton:
            pass
            # Toggle mode (for simplicity; could use buttons)
            # self.mode = "box" if self.mode == "point" else "point"
            # print(f"Mode switched to: {self.mode}")

    def mouseReleaseEvent(self, event):
        """Undo the last selected point on right-click."""
        if (
            event.button() == Qt.MouseButton.RightButton
            and self.mode == "manual"
            and self.temp_points
        ):
            if self.temp_points:
                _ = self.temp_points.pop()
                self.image_scene.removeItem(self.temp_ellipses.pop())
            if self.temp_lines:
                self.image_scene.removeItem(self.temp_lines.pop())

            if self.temp_polygon:
                self.image_scene.removeItem(self.temp_polygon)

            if len(self.temp_points) >= 2:
            pos = self.mapToScene(event.pos())
            temp_poly = QPolygonF(self.temp_points + [pos])
            self.temp_polygon = self.image_scene.addPolygon(
                temp_poly,
                pen=QPen(Qt.GlobalColor.black),
                brush=QBrush(QColor(255, 255, 0, 128)),
            )
        return super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Spy on mouse move events from the main window."""
        if (
            event.type() == QEvent.Type.MouseMove
            and self.mode == "manual"
            and len(self.temp_points) >= 2
        ):
            pos = self.mapToScene(event.pos())
            if self.temp_polygon:
                self.image_scene.removeItem(self.temp_polygon)

            temp_poly = QPolygonF(self.temp_points + [pos])
            self.temp_polygon = self.image_scene.addPolygon(
                temp_poly,
                pen=QPen(Qt.GlobalColor.black),
                brush=QBrush(QColor(255, 255, 0, 128)),
            )
        return super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_N and self.mode == "manual" and self.temp_points:
            # Remove temporary polygon and lines if they exist
            if self.temp_polygon:
                self.image_scene.removeItem(self.temp_polygon)
                self.temp_polygon = None

            # Create final polygon
            final_poly = QPolygonF(self.temp_points)
            polygon_item = self.image_scene.addPolygon(
                final_poly,
                pen=QPen(Qt.GlobalColor.black),
                brush=QBrush(QColor(255, 255, 0, 128)),
            )
            self.polygon_items.append(polygon_item)

            # Clear temporary drawing data
            for line in self.temp_lines:
                self.image_scene.removeItem(line)
            self.temp_lines = []
            self.temp_points = []

            # Add movable vertices to the final polygon
            for i, point in enumerate(final_poly):
                vertex_item = VertexItem(point.x() - 3, point.y() - 3, 6, 6)
                vertex_item.setBrush(Qt.GlobalColor.black)
                vertex_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
                vertex_item.setData(0, polygon_item)
                vertex_item.setData(1, i)
                self.image_scene.addItem(vertex_item)
        return super().keyPressEvent(event)

    def resizeEvent(self, event):
        """Adjust image scaling dynamically when the window is resized."""
        super().resizeEvent(event)
        # If an image is loaded, fit it to the new view size
        if self.image_item:
            self.fitInView(self.image_item, Qt.AspectRatioMode.KeepAspectRatio)
