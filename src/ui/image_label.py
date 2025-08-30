from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap, QCursor
from PyQt6.QtCore import Qt, QSize, QPoint
from typing import Optional, Callable

class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(1, 1)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background-color: #333333;")

        # 원본/표시 픽스맵 저장
        self._original_pixmap: Optional[QPixmap] = None

        # 드래그 팬 관련 상태
        self._is_dragging = False
        self._drag_start_pos: Optional[QPoint] = None
        self._h_scroll_value_at_press = 0
        self._v_scroll_value_at_press = 0
        self._scroll_area = None  # 외부에서 주입 (QScrollArea)

        # 줌 휠 처리 콜백(외부 주입). signature: (delta_y:int, ctrl:bool, vp_anchor:QPoint)
        self._wheel_zoom_callback: Optional[Callable[[int, bool, QPoint], None]] = None

    def setScrollArea(self, scroll_area):
        self._scroll_area = scroll_area

    def setWheelZoomCallback(self, callback):
        self._wheel_zoom_callback = callback

    def setPixmap(self, pixmap):
        if pixmap and not pixmap.isNull():
            self._original_pixmap = pixmap
        else:
            self._original_pixmap = None
        super().setPixmap(pixmap)
        if pixmap and not pixmap.isNull():
            self.setFixedSize(pixmap.size())
        self.adjustSize()

    def setDisplayedPixmap(self, pixmap: Optional[QPixmap]):
        # 표시용 픽스맵만 교체 (원본 유지)
        super().setPixmap(pixmap)
        if pixmap and not pixmap.isNull():
            # 스케일된 픽스맵 크기에 맞춰 위젯 크기를 고정해 스크롤/맞춤을 정확히 반영
            self.setFixedSize(pixmap.size())
        self.adjustSize()

    def originalPixmap(self) -> Optional[QPixmap]:
        return self._original_pixmap

    def sizeHint(self):
        return QSize(480, 320)

    # 드래그 팬 구현
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._scroll_area:
            hbar = self._scroll_area.horizontalScrollBar()
            vbar = self._scroll_area.verticalScrollBar()
            # 스크롤바가 실제로 필요할 때만 드래그 팬 활성화
            if (hbar.maximum() > 0) or (vbar.maximum() > 0):
                self._is_dragging = True
                self._drag_start_pos = event.position().toPoint()
                self._h_scroll_value_at_press = hbar.value()
                self._v_scroll_value_at_press = vbar.value()
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging and self._scroll_area and self._drag_start_pos is not None:
            delta = event.position().toPoint() - self._drag_start_pos
            hbar = self._scroll_area.horizontalScrollBar()
            vbar = self._scroll_area.verticalScrollBar()
            hbar.setValue(self._h_scroll_value_at_press - delta.x())
            vbar.setValue(self._v_scroll_value_at_press - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            self._drag_start_pos = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # 마우스 휠 줌 훅
    def wheelEvent(self, event):
        if self._wheel_zoom_callback and self._scroll_area:
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            delta_y = event.angleDelta().y()
            # 뷰포트 기준 앵커 좌표 계산
            vp_anchor = self._scroll_area.viewport().mapFrom(self, event.position().toPoint())
            self._wheel_zoom_callback(delta_y, ctrl, vp_anchor)
            event.accept()
            return
        super().wheelEvent(event)