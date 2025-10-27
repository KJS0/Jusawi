from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint, QEasingCurve, QPropertyAnimation  # type: ignore[import]
from PyQt6.QtGui import QCursor  # type: ignore[import]


def apply_ui_chrome_visibility(viewer, visible: bool, temporary: bool = False) -> None:
    viewer._ui_chrome_visible = bool(visible)
    if not viewer.is_fullscreen:
        try:
            if hasattr(viewer, 'button_bar') and viewer.button_bar:
                viewer.button_bar.setVisible(bool(visible))
        except Exception:
            pass
        try:
            viewer.statusBar().setVisible(bool(visible))
        except Exception:
            pass
        try:
            if hasattr(viewer, 'filmstrip') and viewer.filmstrip is not None:
                viewer.filmstrip.setVisible(bool(visible))
        except Exception:
            pass
        try:
            if hasattr(viewer, '_rating_flag_bar') and viewer._rating_flag_bar is not None:
                viewer._rating_flag_bar.setVisible(bool(visible))
        except Exception:
            pass
        return
    if temporary and not bool(visible):
        try:
            vp = viewer.image_display_area.viewport()
            vw, vh = vp.width(), vp.height()
        except Exception:
            vw = getattr(viewer, 'width', lambda: 0)()
            vh = getattr(viewer, 'height', lambda: 0)()
        try:
            if hasattr(viewer, 'button_bar') and viewer.button_bar:
                try:
                    h = int(getattr(viewer, '_fs_toolbar_h', None) or viewer.button_bar.sizeHint().height())
                except Exception:
                    h = int(viewer.button_bar.height()) if viewer.button_bar.height() > 0 else 32
                viewer.button_bar.setVisible(False)
                viewer.button_bar.move(0, -int(h))
        except Exception:
            pass
        try:
            if hasattr(viewer, 'filmstrip') and viewer.filmstrip:
                try:
                    fh = int(max(1, int(getattr(viewer, '_fs_filmstrip_h', None) or viewer.filmstrip.sizeHint().height())))
                except Exception:
                    fh = int(max(1, viewer.filmstrip.height())) if viewer.filmstrip.height() > 0 else 64
                viewer.filmstrip.setVisible(False)
                viewer.filmstrip.move(0, int(vh))
        except Exception:
            pass
    else:
        try:
            animate_fs_overlay(viewer, visible)
        except Exception:
            pass
    try:
        if hasattr(viewer, '_rating_flag_bar') and viewer._rating_flag_bar is not None:
            viewer._rating_flag_bar.setVisible(bool(visible) and (not viewer.is_fullscreen))
    except Exception:
        pass


def update_info_overlay_text(viewer) -> None:
    if getattr(viewer, "_info_overlay", None) is None:
        return
    try:
        path = viewer.current_image_path or ""
        name = viewer._basename_cache if hasattr(viewer, "_basename_cache") else None
        if not name:
            name = (path and __import__('os').path.basename(path)) or "-"
            viewer._basename_cache = name
    except Exception:
        name = "-"
    try:
        w = int(getattr(viewer.image_display_area, "_natural_width", 0) or 0)
        h = int(getattr(viewer.image_display_area, "_natural_height", 0) or 0)
    except Exception:
        w = h = 0
    try:
        scale_pct = int(round(float(getattr(viewer, "_last_scale", 1.0) or 1.0) * 100))
    except Exception:
        scale_pct = 100
    txt = f"{name}\n해상도: {w} x {h}\n배율: {scale_pct}%"
    try:
        viewer._info_overlay.setText(txt)
    except Exception:
        pass


def on_user_activity(viewer) -> None:
    if not viewer.is_fullscreen:
        return
    try:
        ensure_fs_overlays_created(viewer)
    except Exception:
        pass
    # 마우스가 툴바/필름스트립 위에 있으면 자동 숨김 타이머를 시작하지 않음
    if _is_mouse_over_ui_chrome(viewer):
        # UI는 보이도록 유지하고 기존 타이머를 중지
        apply_ui_chrome_visibility(viewer, True, temporary=True)
        try:
            viewer._ui_auto_hide_timer.stop()
        except Exception:
            pass
        try:
            viewer._cursor_hide_timer.stop()
        except Exception:
            pass
        restore_cursor(viewer)
        return
    if int(getattr(viewer, "_fs_auto_hide_ms", 0)) > 0:
        apply_ui_chrome_visibility(viewer, True, temporary=True)
        try:
            viewer._ui_auto_hide_timer.start(int(viewer._fs_auto_hide_ms))
        except Exception:
            pass
    if int(getattr(viewer, "_fs_auto_hide_cursor_ms", 0)) > 0:
        restore_cursor(viewer)
        try:
            viewer._cursor_hide_timer.start(int(viewer._fs_auto_hide_cursor_ms))
        except Exception:
            pass


def start_auto_hide_timers(viewer) -> None:
    if not viewer.is_fullscreen:
        return
    # 마우스가 UI 크롬 위면 시작하지 않음
    if _is_mouse_over_ui_chrome(viewer):
        return
    try:
        if int(getattr(viewer, "_fs_auto_hide_ms", 0)) > 0:
            viewer._ui_auto_hide_timer.start(int(viewer._fs_auto_hide_ms))
        if int(getattr(viewer, "_fs_auto_hide_cursor_ms", 0)) > 0:
            viewer._cursor_hide_timer.start(int(viewer._fs_auto_hide_cursor_ms))
    except Exception:
        pass


def hide_cursor_if_fullscreen(viewer) -> None:
    if not viewer.is_fullscreen:
        return
    # 마우스가 UI 크롬(툴바/필름스트립) 위면 커서 숨김 금지
    if _is_mouse_over_ui_chrome(viewer):
        return
    try:
        viewer.setCursor(Qt.CursorShape.BlankCursor)
        viewer.image_display_area.viewport().setCursor(Qt.CursorShape.BlankCursor)
    except Exception:
        pass


def restore_cursor(viewer) -> None:
    try:
        viewer.unsetCursor()
        viewer.image_display_area.viewport().setCursor(Qt.CursorShape.ArrowCursor)
    except Exception:
        pass


def _is_mouse_over_ui_chrome(viewer) -> bool:
    try:
        gp = QCursor.pos()
        # 툴바 영역
        try:
            if hasattr(viewer, 'button_bar') and viewer.button_bar and viewer.button_bar.isVisible():
                r = viewer.button_bar.rect()
                tl = viewer.button_bar.mapToGlobal(r.topLeft())
                if (gp.x() >= tl.x() and gp.x() <= tl.x() + r.width() and
                        gp.y() >= tl.y() and gp.y() <= tl.y() + r.height()):
                    return True
        except Exception:
            pass
        # 필름스트립 영역
        try:
            if hasattr(viewer, 'filmstrip') and viewer.filmstrip and viewer.filmstrip.isVisible():
                r2 = viewer.filmstrip.rect()
                tl2 = viewer.filmstrip.mapToGlobal(r2.topLeft())
                if (gp.x() >= tl2.x() and gp.x() <= tl2.x() + r2.width() and
                        gp.y() >= tl2.y() and gp.y() <= tl2.y() + r2.height()):
                    return True
        except Exception:
            pass
        return False
    except Exception:
        return False


def ensure_fs_overlays_created(viewer) -> None:
    vp = viewer.image_display_area.viewport()
    try:
        if hasattr(viewer, 'button_bar') and viewer.button_bar and viewer.button_bar.parent() is not vp:
            viewer.button_bar.setParent(vp)
            try:
                viewer.button_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            except Exception:
                pass
            viewer.button_bar.setStyleSheet("background-color: rgba(0,0,0,160);")
            viewer.button_bar.raise_()
    except Exception:
        pass
    try:
        if hasattr(viewer, 'filmstrip') and viewer.filmstrip and viewer.filmstrip.parent() is not vp:
            viewer.filmstrip.setParent(vp)
            try:
                try:
                    viewer.filmstrip.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                except Exception:
                    pass
                viewer.filmstrip.viewport().setStyleSheet("background-color: rgba(0,0,0,160);")
            except Exception:
                pass
            viewer.filmstrip.raise_()
    except Exception:
        pass


def position_fullscreen_overlays(viewer) -> None:
    if not viewer.is_fullscreen:
        return
    vp = viewer.image_display_area.viewport()
    vw, vh = vp.width(), vp.height()

    def _set_if_diff(widget, x, y, w, h):
        try:
            g = widget.geometry()
            if g.x() == int(x) and g.y() == int(y) and g.width() == int(w) and g.height() == int(h):
                return
        except Exception:
            pass
        try:
            widget.setGeometry(int(x), int(y), int(w), int(h))
        except Exception:
            pass

    try:
        if hasattr(viewer, 'button_bar') and viewer.button_bar:
            try:
                h = int(getattr(viewer, '_fs_toolbar_h', None) or viewer.button_bar.sizeHint().height())
            except Exception:
                h = int(viewer.button_bar.height()) if viewer.button_bar.height() > 0 else 32
            y = 0 if bool(viewer._ui_chrome_visible) else -h
            _set_if_diff(viewer.button_bar, 0, y, vw, h)
    except Exception:
        pass
    try:
        if hasattr(viewer, 'filmstrip') and viewer.filmstrip:
            try:
                fh = int(max(1, int(getattr(viewer, '_fs_filmstrip_h', None) or viewer.filmstrip.sizeHint().height())))
            except Exception:
                fh = int(max(1, viewer.filmstrip.height())) if viewer.filmstrip.height() > 0 else 64
            y = (vh - fh) if (bool(viewer._ui_chrome_visible) and bool(getattr(viewer, "_fs_show_filmstrip_overlay", False))) else vh
            _set_if_diff(viewer.filmstrip, 0, y, vw, fh)
    except Exception:
        pass


def animate_fs_overlay(viewer, show: bool) -> None:
    if not viewer.is_fullscreen:
        return
    vp = viewer.image_display_area.viewport()
    vw, vh = vp.width(), vp.height()
    duration = 220
    if hasattr(viewer, 'button_bar') and viewer.button_bar:
        h = int(viewer.button_bar.sizeHint().height())
        end_y = 0 if show else -h
        try:
            viewer._anim_toolbar.stop()
        except Exception:
            pass
        try:
            viewer.button_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            viewer.button_bar.setStyleSheet("background-color: rgba(0,0,0,160);")
        except Exception:
            pass
        viewer._anim_toolbar = QPropertyAnimation(viewer.button_bar, b"pos", viewer)
        viewer._anim_toolbar.setDuration(duration)
        viewer._anim_toolbar.setEasingCurve(QEasingCurve.Type.OutCubic)
        viewer._anim_toolbar.setStartValue(viewer.button_bar.pos())
        viewer._anim_toolbar.setEndValue(QPoint(0, end_y))
        try:
            if show:
                viewer.button_bar.setVisible(True)
                viewer.button_bar.raise_()
            else:
                viewer._anim_toolbar.finished.connect(lambda: viewer.button_bar.setVisible(False))
        except Exception:
            pass
        viewer._anim_toolbar.start()
    if hasattr(viewer, 'filmstrip') and viewer.filmstrip:
        fh = int(max(1, viewer.filmstrip.sizeHint().height()))
        end_y = (vh - fh) if (show and bool(getattr(viewer, "_fs_show_filmstrip_overlay", False))) else vh
        try:
            viewer._anim_filmstrip.stop()
        except Exception:
            pass
        viewer._anim_filmstrip = QPropertyAnimation(viewer.filmstrip, b"pos", viewer)
        viewer._anim_filmstrip.setDuration(duration)
        viewer._anim_filmstrip.setEasingCurve(QEasingCurve.Type.OutCubic)
        viewer._anim_filmstrip.setStartValue(viewer.filmstrip.pos())
        viewer._anim_filmstrip.setEndValue(QPoint(0, end_y))
        try:
            if show and bool(getattr(viewer, "_fs_show_filmstrip_overlay", False)):
                viewer.filmstrip.setVisible(True)
                viewer.filmstrip.raise_()
            elif not show:
                viewer._anim_filmstrip.finished.connect(lambda: viewer.filmstrip.setVisible(False))
        except Exception:
            pass
        viewer._anim_filmstrip.start()


def restore_overlays_to_layout(viewer) -> None:
    try:
        if hasattr(viewer, 'button_bar') and viewer.button_bar:
            try:
                viewer.button_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
            except Exception:
                pass
            viewer.button_bar.setStyleSheet("")
            try:
                viewer.button_bar.setParent(viewer.centralWidget())
            except Exception:
                viewer.button_bar.setParent(viewer)
            try:
                viewer.main_layout.insertWidget(0, viewer.button_bar)
            except Exception:
                pass
            try:
                viewer.button_bar.update()
                viewer.button_bar.repaint()
            except Exception:
                pass
    except Exception:
        pass
    try:
        if hasattr(viewer, 'filmstrip') and viewer.filmstrip:
            try:
                viewer.filmstrip.setStyleSheet("")
                try:
                    viewer.filmstrip.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
                    viewer.filmstrip.viewport().setStyleSheet("")
                except Exception:
                    pass
            except Exception:
                pass
            try:
                viewer.filmstrip.setParent(viewer.centralWidget())
            except Exception:
                viewer.filmstrip.setParent(viewer)
            try:
                idx_rb = -1
                try:
                    if hasattr(viewer, '_rating_flag_bar') and viewer._rating_flag_bar is not None:
                        idx_rb = viewer.main_layout.indexOf(viewer._rating_flag_bar)
                except Exception:
                    idx_rb = -1
                if idx_rb is not None and int(idx_rb) >= 0:
                    viewer.main_layout.insertWidget(int(idx_rb), viewer.filmstrip)
                else:
                    viewer.main_layout.addWidget(viewer.filmstrip, 0)
            except Exception:
                pass
            try:
                viewer.filmstrip.update()
                viewer.filmstrip.repaint()
            except Exception:
                pass
    except Exception:
        pass


