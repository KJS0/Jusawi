from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFrame
from PyQt6.QtGui import QPixmap, QTransform, QPainter, QCursor, QColor, QBrush
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPointF

class ImageView(QGraphicsView):
    scaleChanged = pyqtSignal(float)
    cursorPosChanged = pyqtSignal(int, int)  # image-space integer coordinates

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pix_item = None  # type: QGraphicsPixmapItem | None
        self._original_pixmap = None  # type: QPixmap | None

        # View configuration
        self.setRenderHints(self.renderHints() |
                            QPainter.RenderHint.SmoothPixmapTransform |
                            QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor("#373737")))
        self.setMouseTracking(True)
        # 프레임 라인 제거 및 항상 기본 화살표 커서 유지
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        # Zoom state
        self._current_scale = 1.0
        self._fit_mode = True
        self._min_scale = 0.01  # 1%
        self._max_scale = 16.0  # 1600%

    # API 호환: file_utils.load_image_util에서 setPixmap 호출을 사용
    def setPixmap(self, pixmap: QPixmap | None):
        self._scene.clear()
        self._pix_item = None
        self._original_pixmap = None
        if pixmap and not pixmap.isNull():
            self._pix_item = QGraphicsPixmapItem(pixmap)
            self._scene.addItem(self._pix_item)
            self._original_pixmap = pixmap
            # 장면 경계를 이미지 크기로 설정하여 중앙 정렬 기준을 명확히 함
            self._scene.setSceneRect(self._pix_item.boundingRect())
            # 새 이미지 로드시 맞춤 후 중앙으로 이동
            self._fit_mode = True
            self._apply_fit()
            self._center_view()
        else:
            self.resetTransform()
            self._current_scale = 1.0
        self.scaleChanged.emit(self._current_scale)
        # 새 이미지가 설정되면, 현재 마우스 포인터가 가리키는 이미지 좌표를 즉시 갱신
        if self._pix_item and self._original_pixmap:
            vp_point = self.viewport().mapFromGlobal(QCursor.pos())
            self._emit_cursor_pos_at_viewport_point(QPointF(vp_point))

    def originalPixmap(self) -> QPixmap | None:
        return self._original_pixmap

    # Zoom/fitting
    def set_fit_mode(self, enabled: bool):
        self._fit_mode = bool(enabled)
        if self._fit_mode:
            self._apply_fit()
            self._center_view()
        else:
            # keep current scale
            pass

    def _apply_fit(self):
        if not self._pix_item or not self._original_pixmap:
            return
        br = self._pix_item.boundingRect()
        if br.isEmpty():
            return
        # fitInView sets transform internally; we reset first
        self.resetTransform()
        self.fitInView(br, Qt.AspectRatioMode.KeepAspectRatio)
        # Extract resulting uniform scale from transform
        m = self.transform()
        self._current_scale = m.m11()
        self.scaleChanged.emit(self._current_scale)

    def _center_view(self):
        if self._pix_item:
            self.centerOn(self._pix_item)

    def set_min_max_scale(self, min_scale: float, max_scale: float):
        self._min_scale = min_scale
        self._max_scale = max_scale

    def clamp(self, value: float, min_v: float, max_v: float) -> float:
        return max(min_v, min(value, max_v))

    def set_absolute_scale(self, new_scale: float):
        if not self._pix_item:
            return
        clamped = self.clamp(new_scale, self._min_scale, self._max_scale)
        # absolute transform
        t = QTransform()
        t.scale(clamped, clamped)
        self.setTransform(t)
        self._current_scale = clamped
        self._fit_mode = False
        self.scaleChanged.emit(self._current_scale)

    def zoom_step(self, factor: float):
        self.set_absolute_scale(self._current_scale * factor)

    def _dynamic_step(self) -> float:
        s = self._current_scale
        # 낮은 배율에서 크게, 높은 배율에서 작게 변화
        if s < 0.05:
            base = 1.8
        elif s < 0.1:
            base = 1.7
        elif s < 0.25:
            base = 1.6
        elif s < 0.5:
            base = 1.5
        elif s < 1.0:
            base = 1.4
        elif s < 2.0:
            base = 1.35
        elif s < 4.0:
            base = 1.3
        elif s < 8.0:
            base = 1.25
        else:
            base = 1.2
        return base

    def zoom_in(self):
        self._fit_mode = False
        base = self._dynamic_step()
        self.zoom_step(base)

    def zoom_out(self):
        self._fit_mode = False
        base = self._dynamic_step()
        self.zoom_step(1.0 / base)

    def reset_to_100(self):
        self._fit_mode = False
        self.set_absolute_scale(1.0)

    def fit_to_window(self):
        self.set_fit_mode(True)

    def sizeHint(self) -> QSize:
        return QSize(640, 480)

    # Helpers
    def _emit_cursor_pos_at_viewport_point(self, vp_point: QPointF):
        if not self._pix_item or not self._original_pixmap:
            return
        scene_pos = self.mapToScene(int(vp_point.x()), int(vp_point.y()))
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        # Clamp to image bounds
        w = self._original_pixmap.width()
        h = self._original_pixmap.height()
        x = 0 if x < 0 else (w - 1 if x >= w else x)
        y = 0 if y < 0 else (h - 1 if y >= h else y)
        self.cursorPosChanged.emit(x, y)

    # Events
    def wheelEvent(self, event):
        if not self._pix_item:
            return super().wheelEvent(event)
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        if (not ctrl) or shift:
            # Ctrl 단독이 아닌 경우(Shift 포함 포함) 스크롤/확대 모두 하지 않음
            event.accept()
            return
        # Ctrl 단독일 때만 줌 수행
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        # emit cursor pos after zoom at current cursor
        self._emit_cursor_pos_at_viewport_point(event.position())
        event.accept()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        # 드래그 중/후에도 화살표 커서 유지
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def mouseMoveEvent(self, event):
        if self._pix_item:
            self._emit_cursor_pos_at_viewport_point(event.position())
        super().mouseMoveEvent(event)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_mode:
            self._apply_fit()
            self._center_view() 