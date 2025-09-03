from __future__ import annotations

from typing import TYPE_CHECKING
from PyQt6.QtGui import QPixmap  # type: ignore[import]

if TYPE_CHECKING:
    from .main_window import JusawiViewer


def begin_dpr_transition(viewer: "JusawiViewer", guard_ms: int = 160) -> None:
    try:
        viewer._in_dpr_transition = True
        if viewer._dpr_guard_timer.isActive():
            viewer._dpr_guard_timer.stop()
        viewer._dpr_guard_timer.start(int(max(60, guard_ms)))
    except Exception:
        viewer._in_dpr_transition = True


def ensure_screen_signal_connected(viewer: "JusawiViewer") -> None:
    if getattr(viewer, "_screen_signal_connected", False):
        return
    win = None
    try:
        win = viewer.windowHandle() if hasattr(viewer, 'windowHandle') else None
    except Exception:
        win = None
    if win:
        try:
            win.screenChanged.connect(lambda s: on_screen_changed(viewer, s))
            viewer._screen_signal_connected = True
        except Exception:
            viewer._screen_signal_connected = False


def on_screen_changed(viewer: "JusawiViewer", screen) -> None:
    try:
        if screen:
            try:
                screen.logicalDotsPerInchChanged.connect(lambda *a: on_dpi_changed(viewer, *a))
            except Exception:
                pass
    except Exception:
        pass
    begin_dpr_transition(viewer)
    try:
        apply_scaled_pixmap_now(viewer)
    except Exception:
        pass


def on_dpi_changed(viewer: "JusawiViewer", *args) -> None:
    begin_dpr_transition(viewer)
    try:
        apply_scaled_pixmap_now(viewer)
    except Exception:
        pass


def apply_scaled_pixmap_now(viewer: "JusawiViewer") -> None:
    if not viewer.load_successful or not viewer.current_image_path:
        return
    item_anchor_point = None
    try:
        view = viewer.image_display_area
        pix_item = getattr(view, "_pix_item", None)
        if pix_item:
            vp_center = view.viewport().rect().center()
            scene_center = view.mapToScene(vp_center)
            item_anchor_point = pix_item.mapFromScene(scene_center)
    except Exception:
        item_anchor_point = None
    try:
        if viewer._is_current_file_animation():
            return
        if getattr(viewer, "_movie", None):
            return
    except Exception:
        pass
    try:
        cur_scale = float(getattr(viewer, "_last_scale", 1.0) or 1.0)
    except Exception:
        cur_scale = 1.0
    try:
        dpr = float(viewer.image_display_area.viewport().devicePixelRatioF())
    except Exception:
        try:
            dpr = float(viewer.devicePixelRatioF())
        except Exception:
            dpr = 1.0
    prev_dpr = float(getattr(viewer, "_last_dpr", dpr) or dpr)
    dpr_changed = bool(abs(dpr - prev_dpr) > 1e-3)
    view_mode = str(getattr(viewer.image_display_area, "_view_mode", "free") or "free")

    if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
        try:
            if getattr(viewer, "_fullres_image", None) is not None and not viewer._fullres_image.isNull():
                pm = QPixmap.fromImage(viewer._fullres_image)
                viewer.image_display_area.updatePixmapFrame(pm)
                viewer.image_display_area.set_source_scale(1.0)
                viewer.image_display_area.apply_current_view_mode()
                try:
                    if item_anchor_point is not None and getattr(viewer.image_display_area, "_pix_item", None):
                        new_scene_point = viewer.image_display_area._pix_item.mapToScene(item_anchor_point)
                        viewer.image_display_area.centerOn(new_scene_point)
                except Exception:
                    pass
                viewer._last_dpr = dpr
                return
        except Exception:
            pass
    if cur_scale >= 1.0:
        try:
            if getattr(viewer, "_fullres_image", None) is not None and not viewer._fullres_image.isNull():
                pm = QPixmap.fromImage(viewer._fullres_image)
                viewer.image_display_area.updatePixmapFrame(pm)
                viewer.image_display_area.set_source_scale(1.0)
        except Exception:
            pass
        if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
            try:
                viewer.image_display_area.apply_current_view_mode()
            except Exception:
                pass
        if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
            try:
                viewer.image_display_area.apply_current_view_mode()
            except Exception:
                pass
        try:
            if item_anchor_point is not None and getattr(viewer.image_display_area, "_pix_item", None):
                new_scene_point = viewer.image_display_area._pix_item.mapToScene(item_anchor_point)
                viewer.image_display_area.centerOn(new_scene_point)
        except Exception:
            pass
        viewer._last_dpr = dpr
        if getattr(viewer, "_in_dpr_transition", False):
            return
        return
    if getattr(viewer, "_disable_scaled_cache_below_100", False) and cur_scale < 1.0:
        try:
            if getattr(viewer, "_fullres_image", None) is not None and not viewer._fullres_image.isNull():
                pm = QPixmap.fromImage(viewer._fullres_image)
                viewer.image_display_area.updatePixmapFrame(pm)
                viewer.image_display_area.set_source_scale(1.0)
        except Exception:
            pass
        if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
            try:
                viewer.image_display_area.apply_current_view_mode()
            except Exception:
                pass
        try:
            if item_anchor_point is not None and getattr(viewer.image_display_area, "_pix_item", None):
                new_scene_point = viewer.image_display_area._pix_item.mapToScene(item_anchor_point)
                viewer.image_display_area.centerOn(new_scene_point)
        except Exception:
            pass
        viewer._last_dpr = dpr
        return
    try:
        scaled = viewer.image_service.get_scaled_image(viewer.current_image_path, cur_scale, dpr)
    except Exception:
        scaled = None
    if scaled is None or scaled.isNull():
        try:
            if getattr(viewer, "_fullres_image", None) is not None and not viewer._fullres_image.isNull():
                pm_fb = QPixmap.fromImage(viewer._fullres_image)
                viewer.image_display_area.updatePixmapFrame(pm_fb)
                viewer.image_display_area.set_source_scale(1.0)
        except Exception:
            pass
        if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
            try:
                viewer.image_display_area.apply_current_view_mode()
            except Exception:
                pass
        try:
            if item_anchor_point is not None and getattr(viewer.image_display_area, "_pix_item", None):
                new_scene_point = viewer.image_display_area._pix_item.mapToScene(item_anchor_point)
                viewer.image_display_area.centerOn(new_scene_point)
        except Exception:
            pass
        viewer._last_dpr = dpr
        if getattr(viewer, "_in_dpr_transition", False):
            return
        return
    try:
        base_w = int(viewer._fullres_image.width()) if getattr(viewer, "_fullres_image", None) else 0
        base_h = int(viewer._fullres_image.height()) if getattr(viewer, "_fullres_image", None) else 0
        sw = int(scaled.width())
        sh = int(scaled.height())
        s_w = (sw / float(base_w)) / float(dpr) if base_w > 0 else cur_scale
        s_h = (sh / float(base_h)) / float(dpr) if base_h > 0 else cur_scale
        src_scale = max(0.01, min(1.0, min(s_w, s_h)))
    except Exception:
        src_scale = max(0.01, min(1.0, cur_scale))
    try:
        pm_scaled = QPixmap.fromImage(scaled)
        viewer.image_display_area.updatePixmapFrame(pm_scaled)
        viewer.image_display_area.set_source_scale(src_scale)
        if not getattr(viewer.image_display_area, "_natural_width", 0):
            try:
                if getattr(viewer, "_fullres_image", None):
                    viewer.image_display_area._natural_width = int(viewer._fullres_image.width())
                    viewer.image_display_area._natural_height = int(viewer._fullres_image.height())
            except Exception:
                pass
    except Exception:
        pass
    if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
        try:
            viewer.image_display_area.apply_current_view_mode()
        except Exception:
            pass
    elif dpr_changed and getattr(viewer, "_preserve_visual_size_on_dpr_change", False):
        try:
            last_scale = float(getattr(viewer, "_last_scale", 1.0) or 1.0)
            desired_scale = last_scale * (prev_dpr / dpr)
            viewer.image_display_area.set_absolute_scale(desired_scale)
        except Exception:
            pass
    try:
        if item_anchor_point is not None and getattr(viewer.image_display_area, "_pix_item", None):
            new_scene_point = viewer.image_display_area._pix_item.mapToScene(item_anchor_point)
            viewer.image_display_area.centerOn(new_scene_point)
    except Exception:
        pass
    viewer._last_dpr = dpr
    if getattr(viewer, "_in_dpr_transition", False):
        return
    try:
        if getattr(viewer, "_fullres_image", None) is not None and not viewer._fullres_image.isNull():
            ss = float(getattr(viewer.image_display_area, "_source_scale", 1.0) or 1.0)
            if ss < 1.0:
                if viewer._fullres_upgrade_timer.isActive():
                    viewer._fullres_upgrade_timer.stop()
                viewer._fullres_upgrade_timer.start(120)
    except Exception:
        pass


def upgrade_to_fullres_if_needed(viewer: "JusawiViewer") -> None:
    try:
        if not viewer.load_successful or not viewer.current_image_path:
            return
        if viewer._is_current_file_animation() or getattr(viewer, "_movie", None):
            return
        if getattr(viewer, "_fullres_image", None) is None or viewer._fullres_image.isNull():
            return
        ss = float(getattr(viewer.image_display_area, "_source_scale", 1.0) or 1.0)
        if ss >= 1.0:
            return
        item_anchor_point = None
        try:
            view = viewer.image_display_area
            pix_item = getattr(view, "_pix_item", None)
            if pix_item:
                vp_center = view.viewport().rect().center()
                scene_center = view.mapToScene(vp_center)
                item_anchor_point = pix_item.mapFromScene(scene_center)
        except Exception:
            item_anchor_point = None
        pm = QPixmap.fromImage(viewer._fullres_image)
        viewer.image_display_area.updatePixmapFrame(pm)
        viewer.image_display_area.set_source_scale(1.0)
        try:
            if item_anchor_point is not None and getattr(viewer.image_display_area, "_pix_item", None):
                new_scene_point = viewer.image_display_area._pix_item.mapToScene(item_anchor_point)
                viewer.image_display_area.centerOn(new_scene_point)
        except Exception:
            pass
    except Exception:
        pass


