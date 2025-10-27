from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFrame  # type: ignore[import]
from PyQt6.QtGui import QPixmap, QTransform, QPainter, QCursor, QColor, QBrush  # type: ignore[import]
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPointF, QRectF  # type: ignore[import]

class ImageView(QGraphicsView):
    scaleChanged = pyqtSignal(float)
    cursorPosChanged = pyqtSignal(int, int)  # image-space integer coordinates

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pix_item = None  # type: QGraphicsPixmapItem | None
        self._original_pixmap = None  # type: QPixmap | None
        # Transform state (non-destructive view-only)
        self._rotation_degrees = 0  # 0, 90, 180, 270
        self._flip_horizontal = False
        self._flip_vertical = False

        # View configuration
        # 스무딩/안티앨리어싱 강화 + 텍스트/고해상도 최적화
        rh = self.renderHints()
        rh |= QPainter.RenderHint.SmoothPixmapTransform
        rh |= QPainter.RenderHint.Antialiasing
        try:
            rh |= QPainter.RenderHint.HighQualityAntialiasing
        except Exception:
            pass
        try:
            rh |= QPainter.RenderHint.TextAntialiasing
        except Exception:
            pass
        self.setRenderHints(rh)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor("#373737")))
        self.setMouseTracking(True)
        # 프레임 라인 제거 및 항상 기본 화살표 커서 유지
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        # 휠 스크롤에 의한 뷰 스크롤 방지(줌 전용 UX 유지)
        try:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        except Exception:
            pass

        # Zoom state
        self._current_scale = 1.0
        self._fit_mode = True
        self._min_scale = 0.01  # 1%
        self._max_scale = 16.0  # 1600%
        # View mode: 'fit' | 'fit_width' | 'fit_height' | 'actual'
        self._view_mode = 'fit'

        # 애니메이션 관련 상태(표시 전용) — 오버레이 제거에 따라 내부만 유지
        self._is_animation = False
        self._current_frame_index = 0
        self._total_frames = -1  # 미상
        # 소스 스케일 상태: 현재 픽스맵이 원본 대비 어느 배율로 생성되었는지(<=1.0)
        self._source_scale = 1.0
        # 원본(자연) 해상도 — 다운샘플 표시 중에도 좌표계 기준을 일관 유지하기 위함
        self._natural_width = 0
        self._natural_height = 0

    # API 호환: file_utils.load_image_util에서 setPixmap 호출을 사용
    def setPixmap(self, pixmap: QPixmap | None):
        self._scene.clear()
        self._pix_item = None
        self._original_pixmap = None
        if pixmap and not pixmap.isNull():
            self._pix_item = QGraphicsPixmapItem(pixmap)
            self._scene.addItem(self._pix_item)
            self._original_pixmap = pixmap
            # 새 픽스맵은 원본 해상도로 가정(외부에서 교체 시 set_source_scale로 보정)
            self._source_scale = 1.0
            try:
                self._natural_width = int(max(0, pixmap.width()))
                self._natural_height = int(max(0, pixmap.height()))
            except Exception:
                self._natural_width = pixmap.width()
                self._natural_height = pixmap.height()
            # Set origin to center for consistent rotate/flip behavior
            try:
                self._pix_item.setTransformOriginPoint(self._pix_item.boundingRect().center())
            except Exception:
                pass
            # 장면 경계를 이미지 크기로 설정하여 중앙 정렬 기준을 명확히 함
            self._scene.setSceneRect(self._pix_item.boundingRect())
            # 새 이미지 로드시 현재 보기 모드를 강제 적용하여 일관성 보장
            self.apply_current_view_mode()
            # Reapply current transform state to the new item
            self._apply_item_transform()
        else:
            self.resetTransform()
            self._current_scale = 1.0
            self._natural_width = 0
            self._natural_height = 0
        self.scaleChanged.emit(self._current_scale)
        # 새 이미지가 설정되면, 현재 마우스 포인터가 가리키는 이미지 좌표를 즉시 갱신
        if self._pix_item and self._original_pixmap:
            vp_point = self.viewport().mapFromGlobal(QCursor.pos())
            self._emit_cursor_pos_at_viewport_point(QPointF(vp_point))
        # 새 픽스맵 설정 후 오버레이 갱신
        self.viewport().update()

    def originalPixmap(self) -> QPixmap | None:
        return self._original_pixmap

    def updatePixmapFrame(self, pixmap: QPixmap | None) -> None:
        """애니메이션 프레임 갱신: 장면을 초기화하지 않고 현재 항목의 픽스맵만 교체."""
        try:
            if self._pix_item and pixmap and not pixmap.isNull():
                # 현재 보기 모드가 자유 모드일 때 뷰포트 중심을 앵커로 유지
                preserve_anchor = self._view_mode not in ('fit', 'fit_width', 'fit_height')
                item_anchor_point = None
                if preserve_anchor:
                    try:
                        vp_center = self.viewport().rect().center()
                        scene_center = self.mapToScene(vp_center)
                        item_anchor_point = self._pix_item.mapFromScene(scene_center)
                    except Exception:
                        item_anchor_point = None

                self._pix_item.setPixmap(pixmap)
                self._original_pixmap = pixmap
                # 프레임 교체 시에도 소스 스케일은 외부에서 관리되므로 변경하지 않음

                # 프레임 교체 후에도 변환 원점을 항상 center로 고정
                try:
                    self._pix_item.setTransformOriginPoint(self._pix_item.boundingRect().center())
                except Exception:
                    pass

                # 프레임 크기 변경에 대응해 장면 경계 갱신
                try:
                    self._scene.setSceneRect(self._pix_item.sceneBoundingRect())
                except Exception:
                    pass

                # 보기 모드 재적용 또는 앵커 보존 재중앙
                if self._view_mode in ('fit', 'fit_width', 'fit_height'):
                    self.apply_current_view_mode()
                elif preserve_anchor and item_anchor_point is not None:
                    try:
                        new_scene_point = self._pix_item.mapToScene(item_anchor_point)
                        self.centerOn(new_scene_point)
                    except Exception:
                        pass
        except Exception:
            pass

    # 소스 스케일을 외부(컨트롤러)에서 지정하여, 아이템 트랜스폼을 보정한다.
    def set_source_scale(self, src_scale: float) -> None:
        try:
            s = float(src_scale)
        except Exception:
            s = 1.0
        # 너무 작은 값은 UI 표시 오류를 유발하므로 하한 보정
        if s <= 0.01:
            s = 1.0
        self._source_scale = s
        # 현재 뷰 스케일을 유지하되, 아이템 로컬 트랜스폼으로 1/src_scale 적용
        self._apply_item_transform()
        # 맞춤 모드에서는 즉시 재적용하여 뷰 스케일을 보정
        if self._view_mode in ('fit', 'fit_width', 'fit_height'):
            self.apply_current_view_mode()

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
        # 회전/뒤집기만 반영한 경계(소스 스케일 제외)
        w = self._original_pixmap.width()
        h = self._original_pixmap.height()
        if w <= 0 or h <= 0:
            return
        t = QTransform()
        if self._rotation_degrees:
            t.rotate(self._rotation_degrees)
        sx = -1.0 if self._flip_horizontal else 1.0
        sy = -1.0 if self._flip_vertical else 1.0
        if sx != 1.0 or sy != 1.0:
            t.scale(sx, sy)
        br = t.mapRect(QRectF(0, 0, w, h))
        if br.isEmpty():
            return
        vp = self.viewport().rect()
        if vp.isEmpty():
            return
        vp_w = max(1.0, float(vp.width()))
        vp_h = max(1.0, float(vp.height()))
        # 화면 맞춤 여백(%) 적용: 뷰어 설정에서 읽기
        try:
            margin_pct = float(getattr(self.window(), "_fit_margin_pct", 0.0) or 0.0)
        except Exception:
            margin_pct = 0.0
        if margin_pct > 0:
            m = max(0.0, min(40.0, margin_pct)) / 100.0
            vp_w = max(1.0, vp_w * (1.0 - m * 2.0))
            vp_h = max(1.0, vp_h * (1.0 - m * 2.0))
        s_w = vp_w / float(br.width())
        s_h = vp_h / float(br.height())
        desired = min(s_w, s_h)
        # 소스 스케일 보정(아이템 트랜스폼에 1/src_scale가 들어가므로 나눠서 상쇄)
        try:
            src_scale = float(getattr(self, '_source_scale', 1.0) or 1.0)
        except Exception:
            src_scale = 1.0
        effective = desired / (1.0 / src_scale) if src_scale != 0 else desired
        # 적용: 작은 배율에서 계단 현상을 줄이기 위해 하한 해상도 기준을 높여줌
        self.resetTransform()
        t_view = QTransform()
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        t_view.scale(effective, effective)
        self.setTransform(t_view)
        self._current_scale = effective
        self.scaleChanged.emit(self._current_scale)

    def _apply_fit_width(self):
        if not self._pix_item or not self._original_pixmap:
            return
        w = self._original_pixmap.width()
        h = self._original_pixmap.height()
        if w <= 0 or h <= 0:
            return
        t = QTransform()
        if self._rotation_degrees:
            t.rotate(self._rotation_degrees)
        sx = -1.0 if self._flip_horizontal else 1.0
        sy = -1.0 if self._flip_vertical else 1.0
        if sx != 1.0 or sy != 1.0:
            t.scale(sx, sy)
        br = t.mapRect(QRectF(0, 0, w, h))
        img_w = br.width()
        if img_w <= 0:
            return
        vp_w = max(1.0, float(self.viewport().width()))
        try:
            margin_pct = float(getattr(self.window(), "_fit_margin_pct", 0.0) or 0.0)
        except Exception:
            margin_pct = 0.0
        if margin_pct > 0:
            m = max(0.0, min(40.0, margin_pct)) / 100.0
            vp_w = max(1.0, vp_w * (1.0 - m * 2.0))
        desired = vp_w / float(img_w)
        try:
            src_scale = float(getattr(self, '_source_scale', 1.0) or 1.0)
        except Exception:
            src_scale = 1.0
        effective = desired / (1.0 / src_scale) if src_scale != 0 else desired
        clamped = self.clamp(effective, self._min_scale, self._max_scale)
        t_view = QTransform()
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        t_view.scale(clamped, clamped)
        self.setTransform(t_view)
        self._current_scale = clamped
        self.scaleChanged.emit(self._current_scale)
        self._center_view()

    def _apply_fit_height(self):
        if not self._pix_item or not self._original_pixmap:
            return
        w = self._original_pixmap.width()
        h = self._original_pixmap.height()
        if w <= 0 or h <= 0:
            return
        t = QTransform()
        if self._rotation_degrees:
            t.rotate(self._rotation_degrees)
        sx = -1.0 if self._flip_horizontal else 1.0
        sy = -1.0 if self._flip_vertical else 1.0
        if sx != 1.0 or sy != 1.0:
            t.scale(sx, sy)
        br = t.mapRect(QRectF(0, 0, w, h))
        img_h = br.height()
        if img_h <= 0:
            return
        vp_h = max(1.0, float(self.viewport().height()))
        try:
            margin_pct = float(getattr(self.window(), "_fit_margin_pct", 0.0) or 0.0)
        except Exception:
            margin_pct = 0.0
        if margin_pct > 0:
            m = max(0.0, min(40.0, margin_pct)) / 100.0
            vp_h = max(1.0, vp_h * (1.0 - m * 2.0))
        desired = vp_h / float(img_h)
        try:
            src_scale = float(getattr(self, '_source_scale', 1.0) or 1.0)
        except Exception:
            src_scale = 1.0
        effective = desired / (1.0 / src_scale) if src_scale != 0 else desired
        clamped = self.clamp(effective, self._min_scale, self._max_scale)
        t_view = QTransform()
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        t_view.scale(clamped, clamped)
        self.setTransform(t_view)
        self._current_scale = clamped
        self.scaleChanged.emit(self._current_scale)
        self._center_view()

    def apply_current_view_mode(self):
        if self._view_mode == 'fit':
            self._fit_mode = True
            self._apply_fit()
            self._center_view()
        elif self._view_mode == 'fit_width':
            self._fit_mode = False
            self._apply_fit_width()
        elif self._view_mode == 'fit_height':
            self._fit_mode = False
            self._apply_fit_height()
        elif self._view_mode == 'actual':
            self._fit_mode = False
            self.set_absolute_scale(1.0)
            self._center_view()

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
        # 고정 단계 설정이 있으면 우선 사용
        try:
            if bool(getattr(self.window(), "_use_fixed_zoom_steps", False)):
                f = float(getattr(self.window(), "_zoom_step_factor", 1.25) or 1.25)
                return max(1.05, min(2.5, f))
        except Exception:
            pass
        s = self._current_scale
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

    def _dynamic_step_with_precision(self, precise: bool) -> float:
        # 고정 단계 설정이 있으면 우선 사용
        try:
            if bool(getattr(self.window(), "_use_fixed_zoom_steps", False)):
                if precise:
                    pf = float(getattr(self.window(), "_precise_zoom_step_factor", 1.1) or 1.1)
                    return max(1.02, min(1.8, pf))
                f = float(getattr(self.window(), "_zoom_step_factor", 1.25) or 1.25)
                return max(1.05, min(2.5, f))
        except Exception:
            pass
        base = self._dynamic_step()
        if precise:
            return 1.0 + (base - 1.0) * 0.4
        return base

    def zoom_in(self):
        self._fit_mode = False
        self._view_mode = 'free'
        base = self._dynamic_step()
        self.zoom_step(base)

    def zoom_out(self):
        self._fit_mode = False
        self._view_mode = 'free'
        base = self._dynamic_step()
        self.zoom_step(1.0 / base)

    def reset_to_100(self):
        self._fit_mode = False
        self._view_mode = 'actual'
        self.set_absolute_scale(1.0)

    def fit_to_window(self):
        self._view_mode = 'fit'
        self.set_fit_mode(True)

    def fit_to_width(self):
        self._view_mode = 'fit_width'
        self._fit_mode = False
        self._apply_fit_width()

    def fit_to_height(self):
        self._view_mode = 'fit_height'
        self._fit_mode = False
        self._apply_fit_height()

    def sizeHint(self) -> QSize:
        return QSize(640, 480)

    # Helpers
    def _emit_cursor_pos_at_viewport_point(self, vp_point: QPointF):
        if not self._pix_item or not self._original_pixmap:
            return
        scene_pos = self.mapToScene(int(vp_point.x()), int(vp_point.y()))
        # Map to item-local (untransformed) coordinates so rotation/flip are accounted for
        try:
            item_pos = self._pix_item.mapFromScene(scene_pos)
            # item_pos는 현재 픽스맵 좌표계(다운샘플 기준)이므로, 원본 좌표계로 보정
            try:
                ss = float(getattr(self, '_source_scale', 1.0) or 1.0)
            except Exception:
                ss = 1.0
            if ss > 0 and ss != 1.0:
                x = int(round(item_pos.x() / ss))
                y = int(round(item_pos.y() / ss))
            else:
                x = int(item_pos.x())
                y = int(item_pos.y())
        except Exception:
            x = int(scene_pos.x())
            y = int(scene_pos.y())
        # Clamp to image bounds
        # 자연 해상도로 클램프(다운샘플 표시 중에도 좌표계를 원본 기준으로 유지)
        w = int(getattr(self, "_natural_width", 0) or 0)
        h = int(getattr(self, "_natural_height", 0) or 0)
        if w <= 0 or h <= 0:
            # 폴백: 현재 픽스맵 크기
            w = self._original_pixmap.width()
            h = self._original_pixmap.height()
        x = 0 if x < 0 else (w - 1 if x >= w else x)
        y = 0 if y < 0 else (h - 1 if y >= h else y)
        self.cursorPosChanged.emit(x, y)

    def _is_mouse_over_ui_chrome(self) -> bool:
        try:
            win = self.window()
            if win is None:
                return False
            # 마우스 글로벌 좌표
            from PyQt6.QtGui import QCursor  # type: ignore
            gp = QCursor.pos()
            # 툴바 영역
            try:
                if hasattr(win, 'button_bar') and win.button_bar and win.button_bar.isVisible():
                    r = win.button_bar.rect()
                    rp = win.button_bar.mapToGlobal(r.topLeft())
                    rr = QRectF(rp.x(), rp.y(), r.width(), r.height())
                    if rr.contains(gp.x(), gp.y()):
                        return True
            except Exception:
                pass
            # 필름스트립 영역
            try:
                if hasattr(win, 'filmstrip') and win.filmstrip and win.filmstrip.isVisible():
                    r2 = win.filmstrip.rect()
                    rp2 = win.filmstrip.mapToGlobal(r2.topLeft())
                    rr2 = QRectF(rp2.x(), rp2.y(), r2.width(), r2.height())
                    if rr2.contains(gp.x(), gp.y()):
                        return True
            except Exception:
                pass
            return False
        except Exception:
            return False

    # 애니메이션 상태 API (외부에서 설정)
    def set_animation_state(self, is_animation: bool, current_index: int = 0, total_frames: int = -1):
        self._is_animation = bool(is_animation)
        self._current_frame_index = max(0, int(current_index))
        self._total_frames = int(total_frames) if isinstance(total_frames, int) else -1
        # 오버레이 제거: 별도 페인팅 없음

    # paintEvent의 오버레이 렌더링 제거

    # Events
    def wheelEvent(self, event):
        if not self._pix_item:
            return super().wheelEvent(event)
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        # 설정값에 따른 휠 줌 정책
        try:
            requires_ctrl = bool(getattr(self.window(), "_wheel_zoom_requires_ctrl", True))
        except Exception:
            requires_ctrl = True
        try:
            alt_precise = bool(getattr(self.window(), "_wheel_zoom_alt_precise", True))
        except Exception:
            alt_precise = True
        allow_alt = (alt and alt_precise)
        allow_plain = (not requires_ctrl and not ctrl and not alt)
        # 휠 델타: 일부 환경에서 x/y가 0이 되는 문제를 폴백 처리
        dy = event.angleDelta().y()
        if dy == 0:
            try:
                dy = event.angleDelta().x()
            except Exception:
                dy = 0
        if ctrl or allow_alt or allow_plain:
            self._view_mode = 'free'
            base = self._dynamic_step_with_precision(precise=(alt and not ctrl))
            if dy > 0:
                self.zoom_step(base)
            else:
                self.zoom_step(1.0 / base)
            # emit cursor pos after zoom at current cursor
            self._emit_cursor_pos_at_viewport_point(event.position())
            # 전체화면 오버레이(툴바/필름스트립) 위치 재배치(표시 상태는 변경하지 않음)
            try:
                win = self.window()
                if hasattr(win, "_position_fullscreen_overlays"):
                    win._position_fullscreen_overlays()
                # 전체화면에서 줌 중, 마우스가 UI 크롬 위에 없으면 일시 숨김
                if getattr(win, "is_fullscreen", False) and not self._is_mouse_over_ui_chrome():
                    try:
                        win._apply_ui_chrome_visibility(False, temporary=True)
                    except Exception:
                        pass
            except Exception:
                pass
            event.accept()
            return
        # Ctrl/Alt 미포함: 트랙패드 두 손가락 스크롤로 대각선 팬 지원
        try:
            sbx = self.horizontalScrollBar()
            sby = self.verticalScrollBar()
            dx2 = int(event.angleDelta().x())
            dy2 = int(event.angleDelta().y())
            if sbx is not None and dx2:
                try:
                    sbx.setValue(sbx.value() - dx2)
                except Exception:
                    pass
            if sby is not None and dy2:
                try:
                    sby.setValue(sby.value() - dy2)
                except Exception:
                    pass
            # 전체화면에서 팬 중, 마우스가 UI 크롬 위에 없으면 일시 숨김
            try:
                win = self.window()
                if getattr(win, "is_fullscreen", False) and not self._is_mouse_over_ui_chrome():
                    try:
                        win._apply_ui_chrome_visibility(False, temporary=True)
                    except Exception:
                        pass
            except Exception:
                pass
            event.accept()
            return
        except Exception:
            return super().wheelEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        # 드래그 중/후에도 화살표 커서 유지
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        # 팬 상태 시작 플래그 및 전체화면 시 즉시 숨김
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                win = self.window()
                setattr(win, "_is_user_panning", True)
                if getattr(win, "is_fullscreen", False):
                    try:
                        win._apply_ui_chrome_visibility(False, temporary=True)
                    except Exception:
                        pass
        except Exception:
            pass

    def mouseMoveEvent(self, event):
        if self._pix_item:
            self._emit_cursor_pos_at_viewport_point(event.position())
        super().mouseMoveEvent(event)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        # 드래그/팬 중 오버레이 위치 재배치
        try:
            win = self.window()
            if hasattr(win, "_position_fullscreen_overlays"):
                win._position_fullscreen_overlays()
            # 팬 중 플래그 유지 및 전체화면 시 숨김 유지
            try:
                if int(event.buttons()) & int(Qt.MouseButton.LeftButton):
                    setattr(win, "_is_user_panning", True)
                    if getattr(win, "is_fullscreen", False):
                        try:
                            win._apply_ui_chrome_visibility(False, temporary=True)
                        except Exception:
                            pass
                else:
                    setattr(win, "_is_user_panning", False)
            except Exception:
                pass
        except Exception:
            pass

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        # 릴리즈 시에도 한 번 더 고정 위치 재확인
        try:
            win = self.window()
            if hasattr(win, "_position_fullscreen_overlays"):
                win._position_fullscreen_overlays()
            try:
                setattr(win, "_is_user_panning", False)
            except Exception:
                pass
        except Exception:
            pass

    def resizeEvent(self, event):
        # fit 계열이면 항상 재-맞춤하여 화면 맞춤에서 벗어나지 않게 함
        if self._view_mode in ('fit', 'fit_width', 'fit_height'):
            super().resizeEvent(event)
            try:
                self.apply_current_view_mode()
            except Exception:
                pass
            return
        # 자유 줌: 앵커를 보존해 같은 지점을 중심으로 유지
        item_anchor_point = None
        cur_scale = self._current_scale
        if self._pix_item:
            try:
                vp_center = self.viewport().rect().center()
                scene_center = self.mapToScene(vp_center)
                item_anchor_point = self._pix_item.mapFromScene(scene_center)
            except Exception:
                item_anchor_point = None
        super().resizeEvent(event)
        if self._pix_item and item_anchor_point is not None:
            try:
                self.set_absolute_scale(cur_scale)
                new_scene_point = self._pix_item.mapToScene(item_anchor_point)
                self.centerOn(new_scene_point)
            except Exception:
                pass
        # 전체화면 오버레이 위치 업데이트
        try:
            win = self.window()
            # 순환 import 회피: 메서드 존재 여부로 확인
            if hasattr(win, "_position_fullscreen_overlays"):
                win._position_fullscreen_overlays()
        except Exception:
            pass

    def mouseDoubleClickEvent(self, event):
        # 더블클릭 동작 커스터마이즈
        action = str(getattr(self.window(), "_double_click_action", "toggle") or "toggle")
        if action == 'toggle':
            if self._view_mode == 'actual':
                self.fit_to_window()
            else:
                self.reset_to_100()
        elif action == 'fit':
            self.fit_to_window()
        elif action == 'fit_width':
            self.fit_to_width()
        elif action == 'fit_height':
            self.fit_to_height()
        elif action == 'actual':
            self.reset_to_100()
        # 'none' 은 아무 것도 하지 않음
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        # 방향키/페이지/Home/End로 뷰가 스크롤되지 않도록 소비
        key = event.key()
        if key in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_PageUp,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
        ):
            event.accept()
            return
        return super().keyPressEvent(event)

    # ----- Rotate/Flip (view-only non-destructive) -----
    def set_transform_state(self, rotation_degrees: int, flip_horizontal: bool, flip_vertical: bool):
        # normalize rotation to one of {0,90,180,270}
        rot = int(rotation_degrees) % 360
        if rot % 90 != 0:
            # snap to nearest right angle
            rot = (round(rot / 90.0) * 90) % 360
        self._rotation_degrees = rot
        self._flip_horizontal = bool(flip_horizontal)
        self._flip_vertical = bool(flip_vertical)
        self._apply_item_transform()

    def reset_transform_state(self):
        self._rotation_degrees = 0
        self._flip_horizontal = False
        self._flip_vertical = False
        self._apply_item_transform()

    def _apply_item_transform(self):
        if not self._pix_item:
            return
        # Preserve current view anchor for non-fit modes if enabled in settings
        try:
            ap = bool(getattr(self.window(), "_anchor_preserve_on_transform", True))
        except Exception:
            ap = True
        preserve_anchor = ap and (self._view_mode not in ('fit', 'fit_width', 'fit_height'))
        item_anchor_point = None
        if preserve_anchor:
            try:
                # Use viewport center as anchor
                vp_center = self.viewport().rect().center()
                scene_center = self.mapToScene(vp_center)
                item_anchor_point = self._pix_item.mapFromScene(scene_center)
            except Exception:
                item_anchor_point = None
        t = QTransform()
        # Apply rotation first
        if self._rotation_degrees:
            t.rotate(self._rotation_degrees)
        # Apply flips as scales around the origin (center was set as transform origin)
        sx = -1.0 if self._flip_horizontal else 1.0
        sy = -1.0 if self._flip_vertical else 1.0
        if sx != 1.0 or sy != 1.0:
            t.scale(sx, sy)
        # 소스 다운스케일이 적용된 픽스맵이면, 로컬에서 역스케일링하여 시각적 배율 일치
        try:
            ss = float(getattr(self, '_source_scale', 1.0) or 1.0)
        except Exception:
            ss = 1.0
        if ss > 0 and ss != 1.0:
            inv = 1.0 / ss
            t.scale(inv, inv)
        self._pix_item.setTransform(t)
        # Update scene rect to new bounding rect after transform so fit modes work
        try:
            self._scene.setSceneRect(self._pix_item.sceneBoundingRect())
        except Exception:
            pass
        # Re-center to keep the same anchor visible when preserving
        if preserve_anchor and item_anchor_point is not None:
            try:
                new_scene_point = self._pix_item.mapToScene(item_anchor_point)
                self.centerOn(new_scene_point)
            except Exception:
                pass