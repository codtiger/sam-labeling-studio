from typing import Optional
from PyQt6.QtWidgets import (
    QGraphicsPolygonItem,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPixmapItem,
)
from PyQt6.QtCore import Qt, QPointF, QPoint, QEvent, pyqtSignal, QReadWriteLock
from PyQt6.QtGui import (
    QCursor,
    QPixmap,
    QBrush,
    QColor,
    QPolygonF,
    QPen,
    QPainter,
    QMouseEvent,
    QWheelEvent,
)

from dataclasses import dataclass

from .utils import is_inside_rect


class VertexItem(QGraphicsEllipseItem):
    """Custom item for polygon vertices that updates the parent polygon when moved."""

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.data(
            0
        ):
            new_pos = value
            polygon_item = self.data(0)
            index = self.data(1)
            poly = polygon_item.polygon()
            poly[index] = value
            polygon_item.setPolygon(poly)
            return new_pos
        return super().itemChange(change, value)


@dataclass
class MaskData(object):
    def __init__(self, mask_id: int, points: list, lines: list, label):
        self.id = mask_id
        self.lines = lines
        self.points = points
        self.label = label


class ImageViewer(QGraphicsView):

    object_added = pyqtSignal(MaskData)

    def __init__(self, color_dict):
        super().__init__()
        self.image_scene = QGraphicsScene()
        self.setScene(self.image_scene)

        self.object_lock = QReadWriteLock()

        self.color_dict = color_dict
        self.__last__label = None
        self.image_item = None  # QGraphicsPixmapItem for the image
        self.points = []  # List of QPointF for point annotations
        self.boxes = []  # List of [start, end] QPointF pairs for box annotations
        self.current_box = None  # Temporary box during drawing
        self.polygon_items = []  # List of QGraphicsPolygonItem for model results
        self.mask_id = 0
        # self.mode = "Points"  # Current interaction mode: "point" or "box"

        self.temp_points = []  # Temporary points for current polygon
        self.temp_lines = []  # Temporary lines connecting points
        self.temp_polygon = None  # Temporary shaded polygon during drawing
        self.mode = "model"
        self.current_shape = None  # Current shape for manual annotation
        self.prev_shape = None  # Previous shape for pressing N
        self.shaded_poly = None
        self.point_to_shape: dict = {}

        self.dragging_vertex = None
        self.last_pan_pos = None
        self.is_panning = False

        # Optimize rendering
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # Enable panning
        self.setInteractive(True)
        # Important: Hide scrollbars completely
        # self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Mode selection (could be extended via UI buttons)
        # For simplicity, toggle with right-click in this example
        # self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def set_last_label(self, label):
        self.__last__label = label

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
        self.image_scene.clear()
        # self.image_item = QGraphicsPixmapItem(pixmap)
        self.image_item = self.image_scene.addPixmap(pixmap)
        if self.image_item:
            self.setSceneRect(self.image_item.boundingRect())
            scale_x = self.rect().width() / self.image_item.boundingRect().width()
            scale_y = self.rect().height() / self.image_item.boundingRect().height()
            self.image_scale = min(scale_x, scale_y)

            # Reset the view's transformation matrix
            self.resetTransform()

            # Scale to fit
            self.scale(self.image_scale, self.image_scale)

            # Center the image in the view
            self.centerOn(self.image_item)
            # self.fitInView(self.image_item, Qt.AspectRatioMode.KeepAspectRatio)

    def set_shape(self, shape):
        if self.mode == "manual":
            self.current_shape = shape
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.clear_temp()

    def clear(self):
        """Clear all annotations and reset the scene."""
        self.object_lock.lockForWrite()
        self.image_scene.clear()
        self.image_item = None
        self.points = []
        self.boxes = []
        self.shaded_poly = None
        self.current_box = None
        self.polygon_items = []
        self.temp_points = []
        self.temp_lines = []
        self.temp_ellipses = []
        if self.temp_polygon:
            self.image_scene.removeItem(self.temp_polygon)
            del self.temp_polygon
            self.temp_polygon = None
        self.object_lock.unlock()

    def display_polygons(self, mask_data_list: list[MaskData]):
        """Display polygons returned by the model with editable vertices."""
        # if self.image_item:
        #     self.image_item.setOpacity(0.5)
        self.polygon_items = []
        for mask_data in mask_data_list:
            qpoly = QPolygonF([QPointF(x, y) for x, y in mask_data.points])
            polygon_item = self.image_scene.addPolygon(
                qpoly,
                pen=QColor(*self.color_dict[mask_data.label]),
                # brush=QBrush(QColor(0, 255, 0, 128)),
            )
            if polygon_item:
                polygon_item.setData(0, mask_data.id)
                polygon_item.setData(1, mask_data.label)
                self.polygon_items.append(polygon_item)
                # Add movable vertices
                for i, point in enumerate(qpoly):
                    vertex_item = VertexItem(0, 0, 20, 20)
                    vertex_item.setPos(point.x() - 3, point.y() - 3)
                    vertex_item.setBrush(QColor(*self.color_dict[mask_data.label]))
                    vertex_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
                    vertex_item.setData(0, polygon_item)  # Reference to polygon
                    vertex_item.setData(1, i)  # Index in polygon
                    self.image_scene.addItem(vertex_item)

    def highlight_polygon(self, index):
        """Highlight the selected polygon."""
        # TODO: handle deletion of polygons
        self.object_lock.lockForRead()
        item = self.polygon_items[index]
        item.setBrush(QBrush(QColor(*self.color_dict[item.data(1)] + (50,))))
        self.object_lock.unlock()

    def unhighlight_polygon(self, index):
        """Clear the highlighted polygon."""
        # TODO: handle deletion of polygons
        self.object_lock.lockForRead()
        item: QGraphicsPolygonItem = self.polygon_items[index]
        item.setBrush(Qt.GlobalColor.transparent)
        self.object_lock.unlock()

    def changePolygonLabel(self, index, label):
        """A label change that should case the polygon color change"""
        self.object_lock.lockForRead()
        item: QGraphicsPolygonItem = self.polygon_items[index]
        item.setData(1, label)
        item.setPen(QColor(*self.color_dict[item.data(1)]))
        item.setBrush(Qt.GlobalColor.transparent)
        for vertex_item in item.data(2):
            vertex_item.setBrush(QBrush(QColor(*self.color_dict[item.data(1)])))

        self.object_lock.unlock()

    def mousePressEvent(self, event):
        """Handle mouse press for point or box annotation."""
        pos = self.mapToScene(event.pos())
        if event.button() == Qt.MouseButton.LeftButton and self.mode == "manual":
            # "NORMAL" mode(like vim). No shape selected.
            if self.current_shape is None:
                item = self.image_scene.itemAt(pos, self.transform())
                # Check if an old polygon's ellipses is clicked for edit
                if isinstance(item, VertexItem):
                    self.is_panning = False
                    self.dragging_vertex = item
                # Moving the image around
                else:
                    self.is_panning = True
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                    self.last_pan_pos = event.pos()

            elif self.current_shape == "polygon":
                self.temp_points.append(pos)
                ellipse = self.image_scene.addEllipse(
                    pos.x() - 6, pos.y() - 6, 15, 15, brush=Qt.GlobalColor.red
                )
                self.temp_ellipses.append(ellipse)
                # LOOK AT THIS
                if len(self.temp_points) == 2:
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
        if event.button() == Qt.MouseButton.LeftButton:
            if self.dragging_vertex:
                self.dragging_vertex = None
                self.current_shape = None
            elif self.is_panning:
                self.setFocus()
                self.is_panning = False
                self.last_pan_pos = None
                self.setCursor(Qt.CursorShape.ArrowCursor)
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
                    brush=QBrush(QColor(*self.color_dict[self.__last__label] + (50,))),
                )
        return super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.pos())
        """Spy on mouse move events from the main window."""
        if (
            self.current_shape == "polygon"
            and len(self.temp_points) >= 2
            and is_inside_rect(self.image_scene.sceneRect(), pos)
        ):
            if self.temp_polygon:
                self.image_scene.sceneRect
                self.image_scene.removeItem(self.temp_polygon)

            temp_poly = QPolygonF(self.temp_points + [pos])
            self.temp_polygon = self.image_scene.addPolygon(
                temp_poly,
                pen=QPen(Qt.GlobalColor.black),
                brush=QBrush(QColor(*self.color_dict[self.__last__label] + (50,))),
            )
        elif self.current_shape is None:
            if self.dragging_vertex:
                rect = self.dragging_vertex.rect()
                self.dragging_vertex.setPos(pos.x() - 10, pos.y() - 10)
                self.image_scene.update()
                # self.dragging_vertex.setVisible(True)
            elif self.is_panning:
                if self.last_pan_pos is not None:
                    delta = event.pos() - self.last_pan_pos

                    delta_scene = self.mapToScene(delta) - self.mapToScene(QPoint(0, 0))
                    current_transform = self.transform()
                    self.setSceneRect(
                        self.sceneRect().translated(
                            -delta_scene.x() * current_transform.m11() * 2,
                            -delta_scene.y() * current_transform.m22() * 2,
                        )
                    )
                    self.last_pan_pos = event.pos()
                #     self.horizontalScrollBar().setValue(
                #         self.horizontalScrollBar().value() - delta.x()
                #     self.verticalScrollBar().setValue(
                #         self.verticalScrollBar().value() - delta.y()
                #     self.last_pan_pos = event.pos()  # Update last position
                # rect = self.image_item.boundingRect().getRect()
                # if rect:
                #     new_x, new_y = (
                #         rect[0] + (self.last_pan_pos.x() - pos.x()),
                #         rect[1] + (self.last_pan_pos.y() - pos.y()),
                #     )

                # self.setSceneRect(new_x, new_y, rect[2], rect[3])
            elif len(self.image_scene.items()) > 1:
                item = self.image_scene.itemAt(pos, self.transform())
                if isinstance(item, QGraphicsPolygonItem):
                    mask_id, label = item.data(0), item.data(1)
                    item.setBrush(QColor(*self.color_dict[label] + (50,)))
                    self.shaded_poly = item
                elif self.shaded_poly is not None:
                    self.shaded_poly.setBrush(Qt.GlobalColor.transparent)

        return super().mouseMoveEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        # Zoom in/out with mouse wheel
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor

        # Save the scene point under cursor
        old_pos = self.mapToScene(event.position().toPoint())

        # Zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoomInFactor
        else:
            zoom_factor = zoomOutFactor

        # Apply zoom
        print(zoom_factor)
        self.scale(zoom_factor, zoom_factor)

        # Get the new position under cursor
        new_pos = self.mapToScene(event.position().toPoint())

        # Move scene to keep the point under the cursor
        delta = new_pos - old_pos
        # Move scene to keep the point under the cursor
        delta = new_pos - old_pos

        if event.angleDelta().y() > 0:
            self.setSceneRect(self.sceneRect().translated(-delta))
        else:
            self.setSceneRect(self.sceneRect().translated(-delta))

        event.accept()
        return super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event: Optional[QMouseEvent]) -> None:
        """Reset the view to fit the image in the center"""
        if self.image_item:
            # Reset to identity matrix
            self.resetTransform()

            # Fit image to view
            view_rect = self.rect()
            pixmap_rect = self.image_item.boundingRect()
            self.setSceneRect(pixmap_rect)
            scale_x = view_rect.width() / pixmap_rect.width()
            scale_y = view_rect.height() / pixmap_rect.height()
            scale = min(scale_x, scale_y)

            # Apply the scale
            self.scale(scale, scale)

            # Center the image
            self.centerOn(self.image_item)
        return super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if self.mode == "manual":
            # Finalize current temp_poly, and add it to objects
            if self.prev_shape is not None and self.current_shape is None:
                self.current_shape = self.prev_shape
                self.setCursor(Qt.CursorShape.CrossCursor)

            elif event.key() == Qt.Key.Key_N and self.temp_points:
                if self.temp_polygon:
                    self.image_scene.removeItem(self.temp_polygon)
                    self.temp_polygon = None

                # Create final polygon
                final_poly = QPolygonF(self.temp_points)
                polygon_item = self.image_scene.addPolygon(
                    final_poly,
                    pen=QPen(QColor(*self.color_dict[self.__last__label])),
                    # brush=QBrush(QColor(255, 255, 0, 128)),
                )
                if polygon_item:
                    polygon_item.setData(0, self.mask_id)  # poly_id
                    polygon_item.setData(1, self.__last__label)  # label
                    polygon_item.setData(2, [])  # vertices
                    self.polygon_items.append(polygon_item)

                # Clear temporary drawing data
                for line in self.temp_lines:
                    self.image_scene.removeItem(line)
                for ellipse in self.temp_ellipses:
                    self.image_scene.removeItem(ellipse)
                    polygon_item.setData(1, self.__last__label)
                mask_data = MaskData(
                    self.mask_id, self.temp_points, self.temp_lines, self.__last__label
                )
                self.mask_id += 1
                # emit new mask to the object list
                self.object_added.emit(mask_data)
                self.temp_lines = []
                self.temp_points = []
                self.temp_ellipses = []

                # Add movable vertices to the final polygon
                verteces = []
                for i, point in enumerate(final_poly):
                    vertex_item = VertexItem(0, 0, 15, 15)
                    vertex_item.setPos(point.x() - 5, point.y() - 5)
                    vertex_item.setBrush(
                        QBrush(QColor(*self.color_dict[self.__last__label]))
                    )
                    vertex_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
                    vertex_item.setData(0, polygon_item)
                    vertex_item.setData(1, i)
                    self.image_scene.addItem(vertex_item)
                    verteces.append(vertex_item)

                polygon_item.setData(2, verteces)
                # reset states to NORMAL
                self.prev_shape = self.current_shape
                self.current_shape = None
                self.setCursor(Qt.CursorShape.ArrowCursor)
            # Remove the current temp poly upon pressing ESC
            elif event.key() == Qt.Key.Key_Escape and self.temp_points:
                if self.temp_polygon:
                    self.image_scene.removeItem(self.temp_polygon)
                    for line in self.temp_lines:
                        self.image_scene.removeItem(line)
                    for ellipse in self.temp_ellipses:
                        self.image_scene.removeItem(ellipse)
                    self.temp_polygon = None
                    self.temp_lines = []
                    self.temp_points = []
                    self.temp_ellipses = []

                # return to NORMAL mode
                self.current_shape = None
                self.setCursor(Qt.CursorShape.ArrowCursor)

        return super().keyPressEvent(event)

    def resetView(self, event):
        """Adjust image scaling dynamically when the window is resized."""
        print("shaped")
        super().resizeEvent(event)
        # If an image is loaded, fit it to the new view size
        if self.image_item:
            self.resetTransform()

            # Fit image to view
            view_rect = self.rect()
            pixmap_rect = self.image_item.boundingRect()
            self.setSceneRect(pixmap_rect)
            scale_x = view_rect.width() / pixmap_rect.width()
            scale_y = view_rect.height() / pixmap_rect.height()
            scale = min(scale_x, scale_y)

            # Apply the scale
            self.scale(scale, scale)

            # Center the image
            self.centerOn(self.image_item)
