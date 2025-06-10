from typing import Optional
import logging
import math

from PyQt6.QtWidgets import (
    QGraphicsPolygonItem,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QRubberBand,
)
from PyQt6.QtCore import (
    Qt,
    QSize,
    QPointF,
    QPoint,
    QRect,
    QRectF,
    pyqtSignal,
    QReadWriteLock,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QPolygonF,
    QPen,
    QPainter,
    QMouseEvent,
    QWheelEvent,
    QPainterPath,
)
import numpy as np


from .utils import is_inside_rect, ControlItem, ModelPrompts, MaskData, get_logger

logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)


class VertexItem(QGraphicsEllipseItem):
    """Custom item for polygon vertices that updates the parent polygon when moved."""

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.size = 10

    def paint(self, painter, option, widget=None):
        """Override the paint method to ensure constant size."""
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        rect = QRectF(-self.size / 2, -self.size / 2, self.size, self.size)
        painter.drawEllipse(rect)

    def boundingRect(self):
        """Override boundingRect to match the constant size."""
        return QRectF(-self.size / 2, -self.size / 2, self.size, self.size)

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


class ImageViewer(QGraphicsView):

    object_added = pyqtSignal(MaskData)
    control_change = pyqtSignal(ControlItem)
    object_selected = pyqtSignal(
        MaskData
    )  # Change of selection by hovering, useful for copying objects
    object_deselected = pyqtSignal(int)

    COLOR_CYCLE = [
        Qt.GlobalColor.black,
        Qt.GlobalColor.red,
        Qt.GlobalColor.blue,
        Qt.GlobalColor.yellow,
        Qt.GlobalColor.green,
        Qt.GlobalColor.cyan,
    ]

    def __init__(self, color_dict: dict):
        super().__init__()
        self.image_scene = QGraphicsScene()
        self.setScene(self.image_scene)

        self.object_lock = QReadWriteLock()

        self.color_dict = color_dict
        self.__last_label__ = list(self.color_dict.keys())[0]
        self.image_item = None  # QGraphicsPixmapItem for the image
        self.id_to_poly = {}  # mask_id --> poly dict
        self.boxes = []  # List of [start, end] QPointF pairs for box annotations
        self.current_box = None  # Temporary box during drawing
        self.polygon_items = []  # List of QGraphicsPolygonItem for model results
        self.mask_id = 0

        self.temp_points = []  # Temporary points for current polygon
        self.temp_lines = []  # Temporary lines connecting points
        self.temp_polygon = None  # Temporary shaded polygon during drawing
        self.mode = "model"
        # MANUAL MODE params
        self.current_control = ControlItem.NORMAL  # Current shape for manual annotation
        self.prev_shape = None  # Previous shape for pressing N
        self.shaded_poly = None
        self.point_to_shape: dict = {}
        # MODEL MODE params
        self.prompt_mode = ModelPrompts.POINT
        self.num_prompt_objs = 0
        # one per image, temporary
        self.prompt_star_coords = [[]]
        self.prompt_box_coords = []
        self.prompt_stars = []
        self.prompt_boxes = []

        self.current_prompt_color = ImageViewer.COLOR_CYCLE[0]

        self.dragging_vertex = None
        self.last_pan_pos = None
        self.start_roi_pos = QPoint()
        self.start_box_pos = QPoint()

        self.is_panning = False
        self.is_selecting_roi = False
        self.is_prompt_box = False

        self.rubber_band: QRubberBand

        # Optimize rendering
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # Enable panning
        # self.setInteractive(True)
        # Important: Hide scrollbars completely
        # self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        # Mode selection (could be extended via UI buttons)
        # For simplicity, toggle with right-click in this example
        # self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def set_last_label(self, label):
        if label == "":
            self.__last_label__ = list(self.color_dict.keys())[0]
        else:
            self.__last_label__ = label

    def set_mode(self, mode):
        """Set the current mode: 'model' or 'manual'."""
        self.mode = mode
        if self.mode == "manual" and self.image_item:
            self.image_item.setOpacity(1.0)
        elif self.mode == "model" and self.image_item:
            self.image_item.setOpacity(0.4)
        self.control_change.emit(ControlItem.NORMAL)
        if self.temp_polygon or self.temp_lines:
            self.clear_temp()  # Clear temporary annotations when switching modes

    def clear_temp(self):
        """Clear temporary drawing data."""
        self.temp_points = []
        for line in self.temp_lines:
            self.image_scene.removeItem(line)
            line.deleteLater()
        self.temp_lines = []
        if self.temp_polygon:
            self.image_scene.removeItem(self.temp_polygon)
            # self.temp_polygon = None

    def clear_prompts(self):
        self.num_prompt_objs = 0
        self.current_prompt_color = self.COLOR_CYCLE[0]
        for star_item in self.prompt_stars:
            self.image_scene.removeItem(star_item)
        for rect_item in self.prompt_boxes:
            self.image_scene.removeItem(rect_item)
        self.prompt_stars, self.prompt_boxes = [], []
        self.prompt_star_coords, self.prompt_box_coords = [[]], []

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
            if self.mode == "model":
                self.image_item.setOpacity(0.2)
            # self.fitInView(self.image_item, Qt.AspectRatioMode.KeepAspectRatio)

    def set_control(self, control):
        self.current_control = control
        if self.mode == "manual":
            if control == ControlItem.NORMAL:
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            else:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                self.setCursor(Qt.CursorShape.CrossCursor)
        if self.mode == "model":
            if control == ControlItem.NORMAL:
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            elif control == ControlItem.STAR:
                self.prompt_mode = ModelPrompts.POINT
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                self.setCursor(Qt.CursorShape.CrossCursor)
            elif control == ControlItem.BOX:
                self.prompt_mode = ModelPrompts.BOX
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                self.setCursor(Qt.CursorShape.CrossCursor)
        if self.temp_polygon or self.temp_lines:
            self.clear_temp()

    def clear(self):
        """Clear all annotations and reset the scene."""
        self.object_lock.lockForWrite()
        self.image_scene.clear()
        self.image_item = None
        self.id_to_poly = {}
        self.boxes = []
        self.shaded_poly = None
        self.current_box = None
        self.polygon_items = []
        self.temp_points = []
        self.temp_lines = []
        self.temp_polygon = None
        self.temp_ellipses = []
        self.object_lock.unlock()

    def display_polygons(self, mask_data_list: list[MaskData]):
        """Display polygons loaded by the main ui's object list"""
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
                polygon_item.setData(0, mask_data.id)  # id
                polygon_item.setData(1, mask_data.label)  # label
                vertices = []
                self.id_to_poly[mask_data.id] = polygon_item
                self.polygon_items.append(polygon_item)
                # Add movable vertices
                for i, point in enumerate(qpoly):
                    vertex_item = VertexItem(0, 0, 10, 10)
                    vertex_item.setPos(point.x() - 3, point.y() - 3)
                    vertex_item.setBrush(QColor(*self.color_dict[mask_data.label]))
                    vertex_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
                    vertex_item.setData(0, polygon_item)  # Reference to polygon
                    vertex_item.setData(1, i)  # Index in polygon
                    vertices.append(vertex_item)
                    self.image_scene.addItem(vertex_item)
                polygon_item.setData(2, vertices)

    def add_prediction_polys(self, mask_arr: list[list]):
        """Display polygons returned by the model with editable vertices.
        IMPORTANT: Need to be assigned mask ids by the image viewer"""

        # if self.image_item:
        #     self.image_item.setOpacity(0.5)
        self.polygon_items = []
        masks: list[MaskData] = []
        for mask in mask_arr:
            qpoly = QPolygonF([QPointF(y, x) for x, y in mask])
            polygon_item = self.image_scene.addPolygon(
                qpoly,
                pen=QColor(*self.color_dict["background"]),
                # brush=QBrush(QColor(0, 255, 0, 128)),
            )
            if polygon_item:
                mask_data = MaskData(
                    mask_id=self.mask_id,
                    points=[QPoint(x, y) for x, y in mask],
                    label="background",
                    center=polygon_item.boundingRect().center(),
                )
                masks.append(mask_data)
                polygon_item.setData(0, self.mask_id)
                polygon_item.setData(1, "background")
                vertices = []
                self.polygon_items.append(polygon_item)
                self.id_to_poly[self.mask_id] = polygon_item
                # Add movable vertices
                for i, point in enumerate(qpoly):
                    vertex_item = VertexItem(0, 0, 10, 10)
                    vertex_item.setPos(point.x() - 3, point.y() - 3)
                    vertex_item.setBrush(QColor(*self.color_dict["background"]))
                    vertex_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
                    vertex_item.setData(0, polygon_item)  # Reference to polygon
                    vertex_item.setData(1, i)  # Index in polygon
                    self.image_scene.addItem(vertex_item)
                    vertices.append(vertex_item)
                polygon_item.setData(2, vertices)
                self.mask_id += 1
        return masks

    def update_candidate_mask(self, mask_id, new_mask: list[list]):
        qpoly = QPolygonF([QPointF(coord[1], coord[0]) for coord in new_mask])
        self.object_lock.lockForRead()
        item = self.id_to_poly[mask_id]
        item.setPolygon(qpoly)

        if item and isinstance(item, QGraphicsPolygonItem):
            old_brush = item.data(2).pop(0).brush()
            for vertex_item in item.data(2):
                self.image_scene.removeItem(vertex_item)
                vertex_item = None
            vertices = []
            for i, point in enumerate(qpoly):
                vertex_item = VertexItem(0, 0, 10, 10)
                vertex_item.setPos(point.x() - 3, point.y() - 3)
                vertex_item.setBrush(old_brush)
                vertex_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
                vertex_item.setData(0, item)  # Reference to polygon
                vertex_item.setData(1, i)  # Index in polygon
                self.image_scene.addItem(vertex_item)
                vertices.append(vertex_item)
            item.setData(2, vertices)
        self.object_lock.unlock()

    def highlight_polygon(self, mask_id):
        """Highlight the selected polygon."""
        # TODO: handle deletion of polygons
        self.object_lock.lockForRead()
        item = self.id_to_poly[mask_id]
        if item:
            item.setBrush(QBrush(QColor(*self.color_dict[item.data(1)] + (50,))))
        self.object_lock.unlock()

    def unhighlight_polygon(self, mask_id):
        """Clear the highlighted polygon."""
        # TODO: handle deletion of polygons
        self.object_lock.lockForRead()
        item = self.id_to_poly[mask_id]
        if item:
            item.setBrush(Qt.GlobalColor.transparent)
        self.object_lock.unlock()

    def removePolygon(self, mask_id):
        self.object_lock.lockForWrite()
        poly_item: QGraphicsItem = self.id_to_poly[mask_id]
        for vertex_item in poly_item.data(2):
            self.image_scene.removeItem(vertex_item)
            vertex_item = None
        self.image_scene.removeItem(poly_item)
        self.id_to_poly[mask_id] = None
        self.object_lock.unlock()

    def changePolygonLabel(self, mask_id, label):
        """A label change that should case the polygon color change"""
        self.object_lock.lockForWrite()
        # TODO: handle deletion of polygons
        item: Optional[QGraphicsPolygonItem] = self.id_to_poly[mask_id]
        if item:
            item.setData(1, label)
            item.setPen(QColor(*self.color_dict[item.data(1)]))
            item.setBrush(Qt.GlobalColor.transparent)
            for vertex_item in item.data(2):
                vertex_item.setBrush(QBrush(QColor(*self.color_dict[item.data(1)])))
        self.object_lock.unlock()

    def mousePressEvent(self, event):
        """Handle mouse press for point or box annotation."""
        pos = self.mapToScene(event.pos())
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.mode == "manual"
            and is_inside_rect(self.image_scene.sceneRect(), pos)
        ):
            # "NORMAL" mode(like vim). No shape selected.
            if self.current_control == ControlItem.NORMAL:
                item = self.image_scene.itemAt(pos, self.transform())
                # Check if an old polygon's ellipses is clicked for edit
                if isinstance(item, VertexItem):
                    self.is_panning = False
                    self.dragging_vertex = item
                # Moving the image around if no scrollbar
                elif self.transform().m11() <= 1:
                    self.is_panning = True
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                    self.last_pan_pos = event.pos()

                else:
                    super().mousePressEvent(event)

            elif self.current_control == ControlItem.POLYGON:
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
            elif self.current_control == ControlItem.ROI:
                self.is_selecting_roi = True
                self.start_roi_pos = event.pos()
                self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
                self.rubber_band.setGeometry(QRect(self.start_roi_pos, QSize()))
                self.rubber_band.show()

        elif self.mode == "model":
            if event.button() == Qt.MouseButton.LeftButton and is_inside_rect(
                self.image_scene.sceneRect(), pos
            ):
                if self.prompt_mode == ModelPrompts.POINT:
                    self.prompt_star_coords[-1].append((pos.x(), pos.y()))
                    # Draw a star at that location
                    star_path = QPainterPath()
                    center = pos
                    outer_radius = 15
                    inner_radius = 8
                    for i in range(10):
                        angle = i * 36  # 36 degrees between each point
                        radius = outer_radius if i % 2 == 0 else inner_radius
                        x = center.x() + radius * math.cos(math.radians(angle))
                        y = center.y() + radius * math.sin(math.radians(angle))
                        if i == 0:
                            star_path.moveTo(x, y)
                        else:
                            star_path.lineTo(x, y)
                    star_path.closeSubpath()
                    star_item = self.image_scene.addPath(
                        star_path,
                        QPen(Qt.GlobalColor.yellow),
                        QBrush(self.current_prompt_color),
                    )
                    star_item.setFlag(
                        QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True
                    )
                    star_item.setFlag(
                        QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True
                    )
                    self.prompt_stars.append(star_item)
                elif self.prompt_mode == ModelPrompts.BOX:
                    self.is_prompt_box = True
                    self.start_box_pos = event.pos()
                    self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
                    self.rubber_band.setGeometry(QRect(self.start_box_pos, QSize()))
                    self.rubber_band.show()

        elif event.button() == Qt.MouseButton.RightButton:
            pass
            # Toggle mode (for simplicity; could use buttons)
            # self.mode = "box" if self.mode == "point" else "point"
            # print(f"Mode switched to: {self.mode}")
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.pos())
        """Spy on mouse move events from the main window."""
        if (
            self.current_control == ControlItem.POLYGON
            and len(self.temp_points) >= 2
            and is_inside_rect(self.image_scene.sceneRect(), pos)
        ):
            if self.temp_polygon:
                self.image_scene.removeItem(self.temp_polygon)

            temp_poly = QPolygonF(self.temp_points + [pos])
            self.temp_polygon = self.image_scene.addPolygon(
                temp_poly,
                pen=QPen(Qt.GlobalColor.black),
                brush=QBrush(QColor(*self.color_dict[self.__last_label__] + (50,))),
            )
        else:
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
            elif self.is_selecting_roi:
                rect = QRect(self.start_roi_pos, event.pos()).normalized()
                self.rubber_band.setGeometry(rect)

            elif self.is_prompt_box:
                rect = QRect(self.start_box_pos, event.pos()).normalized()
                self.rubber_band.setGeometry(rect)

            elif len(self.image_scene.items()) > 1:
                item = self.image_scene.itemAt(pos, self.transform())
                if isinstance(item, QGraphicsPolygonItem):
                    mask_id, label, vertices = item.data(0), item.data(1), item.data(2)
                    item.setBrush(QColor(*self.color_dict[label] + (50,)))
                    self.object_selected.emit(
                        MaskData(
                            mask_id=mask_id,
                            label=label,
                            points=[[v.x(), v.y()] for v in vertices],
                            center=item.boundingRect().center(),
                        )
                    )
                    # for vertex in item.data(2):
                    #     vertex.setBrush(
                    #         QBrush(
                    #             Qt.GlobalColor.white,
                    #             style=Qt.BrushStyle.DiagCrossPattern,
                    #         )
                    #     )

                    self.shaded_poly = item
                elif self.shaded_poly is not None:
                    self.shaded_poly.setBrush(Qt.GlobalColor.transparent)
                    self.object_deselected.emit(1)

        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Undo the last selected point on right-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.dragging_vertex:
                self.dragging_vertex = None
                self.current_control = ControlItem.NORMAL
            elif self.is_panning:
                self.setFocus()
                self.is_panning = False
                self.last_pan_pos = None
                self.setCursor(Qt.CursorShape.ArrowCursor)
            elif self.is_selecting_roi:
                rect_view = self.rubber_band.geometry()
                self.rubber_band.hide()
                self.rubber_band.deleteLater()
                self.rubber_band = None

                top_left = self.mapToScene(rect_view.topLeft())
                bottom_right = self.mapToScene(rect_view.bottomRight())
                roi_rect = QRectF(top_left, bottom_right).normalized()

                if roi_rect.isValid() and not roi_rect.isEmpty():
                    self.fitInView(roi_rect, Qt.AspectRatioMode.KeepAspectRatio)

                self.is_selecting_roi = False
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                self.current_control = ControlItem.NORMAL
                self.control_change.emit(ControlItem.NORMAL)
            elif self.is_prompt_box:
                rect_view = self.rubber_band.geometry()
                self.rubber_band.hide()
                self.rubber_band.deleteLater()

                top_left = self.mapToScene(rect_view.topLeft())
                bottom_right = self.mapToScene(rect_view.bottomRight())
                self.prompt_box_coords.append(
                    [top_left.x(), top_left.y(), bottom_right.x(), bottom_right.y()]
                )
                pen = QPen(QColor.fromRgb(220, 12, 12))
                pen.setWidth(5)
                rect = self.image_scene.addRect(
                    QRectF(top_left, bottom_right).normalized(), pen=pen
                )
                self.prompt_boxes.append(rect)
                self.is_prompt_box = False
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                self.current_control = ControlItem.NORMAL
                self.control_change.emit(ControlItem.NORMAL)

        if event.button() == Qt.MouseButton.RightButton and self.mode == "manual":
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
                    brush=QBrush(QColor(*self.color_dict[self.__last_label__] + (50,))),
                )
        return super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        # Zoom in/out with mouse wheel
        zoomInFactor = 1.15
        zoomOutFactor = 1 / zoomInFactor

        # Save the scene point under cursor
        old_pos = self.mapToScene(event.position().toPoint())

        # Zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoomInFactor
        else:
            zoom_factor = zoomOutFactor

        # Apply zoom
        self.scale(zoom_factor, zoom_factor)

        # Get the new position under cursor
        new_pos = self.mapToScene(event.position().toPoint())

        # Move scene to keep the point under the cursor
        delta = new_pos - old_pos

        self.translate(delta.x(), delta.y())
        # if event.angleDelta().y() > 0:
        #     self.setSceneRect(self.sceneRect().translated(-delta))
        # else:
        #     self.setSceneRect(self.sceneRect().translated(-delta))

        event.accept()

    def zoom(self, in_or_out: ControlItem):
        zoomInFactor = 1.15
        zoomOutFactor = 1 / zoomInFactor

        # Zoom
        if in_or_out == ControlItem.ZOOM_IN:
            zoom_factor = zoomInFactor
        else:
            zoom_factor = zoomOutFactor
            logger.warning(f"ZOOMING OUT {zoomOutFactor}")

        # Apply zoom
        self.scale(zoom_factor, zoom_factor)

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
            if event.key() == Qt.Key.Key_N:
                if (
                    self.prev_shape is not None
                    and self.current_control == ControlItem.NORMAL
                ):
                    self.current_control = self.prev_shape
                    self.control_change.emit(self.current_control)
                    self.setCursor(Qt.CursorShape.CrossCursor)

                elif self.temp_points:
                    if self.temp_polygon:
                        self.image_scene.removeItem(self.temp_polygon)
                        self.temp_polygon = None

                    # Create final polygon
                    final_poly = QPolygonF(self.temp_points)
                    polygon_item = self.image_scene.addPolygon(
                        final_poly,
                        pen=QPen(QColor(*self.color_dict[self.__last_label__])),
                        # brush=QBrush(QColor(255, 255, 0, 128)),
                    )
                    if polygon_item:
                        polygon_item.setData(0, self.mask_id)
                        self.id_to_poly[self.mask_id] = polygon_item
                        polygon_item.setData(1, self.__last_label__)  # label
                        polygon_item.setData(2, [])  # vertices
                        self.polygon_items.append(polygon_item)

                    # Clear temporary drawing data
                    for line in self.temp_lines:
                        self.image_scene.removeItem(line)
                    for ellipse in self.temp_ellipses:
                        self.image_scene.removeItem(ellipse)
                        polygon_item.setData(1, self.__last_label__)

                    mask_data = MaskData(
                        self.mask_id,
                        self.temp_points,
                        self.__last_label__,
                        center=polygon_item.boundingRect().center(),
                    )
                    self.object_added.emit(mask_data)
                    self.mask_id += 1
                    # emit new mask to the object list
                    self.temp_lines = []
                    self.temp_points = []
                    self.temp_ellipses = []

                    # Add movable vertices to the final polygon
                    vertices = []
                    for i, point in enumerate(final_poly):
                        vertex_item = VertexItem(0, 0, 15, 15)
                        vertex_item.setPos(point.x() - 5, point.y() - 5)
                        vertex_item.setBrush(
                            QBrush(QColor(*self.color_dict[self.__last_label__]))
                        )
                        vertex_item.setFlag(
                            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                        )
                        vertex_item.setData(0, polygon_item)
                        vertex_item.setData(1, i)
                        self.image_scene.addItem(vertex_item)
                        vertices.append(vertex_item)

                    polygon_item.setData(2, vertices)
                    # reset states to NORMAL
                    self.prev_shape = self.current_control
                    self.current_control = ControlItem.NORMAL
                    self.setCursor(Qt.CursorShape.ArrowCursor)
            # Remove the current temp poly upon pressing ESC
            elif event.key() == Qt.Key.Key_Escape:
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
                self.current_control = ControlItem.NORMAL
                self.control_change.emit(ControlItem.NORMAL)
                self.setCursor(Qt.CursorShape.ArrowCursor)
        if self.mode == "model":
            if event.key() == Qt.Key.Key_N:
                self.prompt_star_coords.append([])
                self.num_prompt_objs = (
                    self.num_prompt_objs + 1
                    if self.num_prompt_objs + 1 < len(ImageViewer.COLOR_CYCLE)
                    else 0
                )
                self.current_prompt_color = ImageViewer.COLOR_CYCLE[
                    self.num_prompt_objs
                ]

        return super().keyPressEvent(event)

    def resetView(self, event):
        """Adjust image scaling dynamically when the window is resized."""
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
