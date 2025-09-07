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
        # 업그레이드 직후 한 틱 동안은 썸네일 재요청을 막아 깜빡임 방지
        if getattr(viewer, "_just_upgraded_fullres", False):
            scaled = None
        else:
            # 자유 모드에서는 현재 배율 기반 캐시를 우선, 맞춤 계열에서는 뷰포트 기반 스케일 디코드를 우선
            if view_mode in ("fit", "fit_width", "fit_height"):
                vp = viewer.image_display_area.viewport().rect()
                vw = int(max(1, vp.width()))
                vh = int(max(1, vp.height()))
                scaled = viewer.image_service.get_scaled_for_viewport(
                    viewer.current_image_path, vw, vh, view_mode=view_mode, dpr=dpr, headroom=1.1
                )
                if (scaled is None or scaled.isNull()) and cur_scale < 1.0:
                    scaled = viewer.image_service.get_scaled_image(viewer.current_image_path, cur_scale, dpr)
            else:
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
        if base_w > 0 and base_h > 0:
            s_w = (sw / float(base_w)) / float(dpr)
            s_h = (sh / float(base_h)) / float(dpr)
            src_scale = max(0.01, min(1.0, min(s_w, s_h)))
        else:
            # 풀해상도 미보유 시 현재 픽스맵을 자연 해상도로 간주
            src_scale = 1.0
    except Exception:
        src_scale = 1.0
    try:
        pm_scaled = QPixmap.fromImage(scaled)
        viewer.image_display_area.updatePixmapFrame(pm_scaled)
        # 자연 해상도가 이미 세팅되어 있으면 그 기준으로 정확한 소스 스케일 재계산
        try:
            nat_w = int(getattr(viewer.image_display_area, "_natural_width", 0) or 0)
            nat_h = int(getattr(viewer.image_display_area, "_natural_height", 0) or 0)
            if nat_w > 0 and nat_h > 0:
                dpr2 = float(viewer.image_display_area.viewport().devicePixelRatioF())
                s_w2 = (pm_scaled.width() / float(nat_w)) / float(dpr2)
                s_h2 = (pm_scaled.height() / float(nat_h)) / float(dpr2)
                src_scale = max(0.01, min(1.0, min(s_w2, s_h2)))
        except Exception:
            pass
        viewer.image_display_area.set_source_scale(src_scale)
        if not getattr(viewer.image_display_area, "_natural_width", 0):
            try:
                if getattr(viewer, "_fullres_image", None):
                    viewer.image_display_area._natural_width = int(viewer._fullres_image.width())
                    viewer.image_display_area._natural_height = int(viewer._fullres_image.height())
            except Exception:
                pass
        # 좌표 즉시 갱신(현재 커서 위치 기준)
        try:
            from PyQt6.QtCore import QPointF  # type: ignore[import]
            from PyQt6.QtGui import QCursor  # type: ignore[import]
            vp_point = viewer.image_display_area.viewport().mapFromGlobal(QCursor.pos())
            viewer.image_display_area._emit_cursor_pos_at_viewport_point(QPointF(vp_point))
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
        ss = float(getattr(viewer.image_display_area, "_source_scale", 1.0) or 1.0)
        # 풀해상도가 아직 없거나 소스 스케일이 1 미만, 혹은 명시적 스케일 프리뷰 플래그가 켜져 있으면 업그레이드 예약
        if ss < 1.0 or getattr(viewer, "_fullres_image", None) is None or viewer._fullres_image.isNull() or getattr(viewer, "_is_scaled_preview", False):
            if viewer._fullres_upgrade_timer.isActive():
                viewer._fullres_upgrade_timer.stop()
            viewer._fullres_upgrade_timer.start(0)
            # 이벤트 루프 다음 틱에 업그레이드 시도
            try:
                from PyQt6.QtCore import QTimer  # type: ignore[import]
                QTimer.singleShot(0, getattr(viewer, "_upgrade_to_fullres_if_needed", lambda: None))
            except Exception:
                pass
    except Exception:
        pass


def upgrade_to_fullres_if_needed(viewer: "JusawiViewer") -> None:
    try:
        if not viewer.load_successful or not viewer.current_image_path:
            return
        if viewer._is_current_file_animation() or getattr(viewer, "_movie", None):
            return
        # 풀해상도가 없으면 지금 디코드하여 업그레이드 준비
        if getattr(viewer, "_fullres_image", None) is None or viewer._fullres_image.isNull():
            try:
                path, img, ok, _ = viewer.image_service.load(viewer.current_image_path)
                if ok and img is not None and not img.isNull():
                    viewer._fullres_image = img
                else:
                    return
            except Exception:
                return
        # 현재 픽스맵이 풀해상도보다 작으면 업그레이드 필요(소스 스케일 값에 의존하지 않음)
        cur_pix = None
        try:
            cur_pix = viewer.image_display_area.originalPixmap()
        except Exception:
            cur_pix = None
        if cur_pix and not cur_pix.isNull():
            try:
                if cur_pix.width() >= viewer._fullres_image.width() and cur_pix.height() >= viewer._fullres_image.height():
                    return
            except Exception:
                pass
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
        # 좌표계를 풀해상도 기준으로 갱신
        try:
            viewer.image_display_area._natural_width = int(viewer._fullres_image.width())
            viewer.image_display_area._natural_height = int(viewer._fullres_image.height())
        except Exception:
            pass
        viewer.image_display_area.set_source_scale(1.0)
        # 맞춤 모드에서는 즉시 재맞춤 적용하여 가시 결과를 보장
        try:
            vm = str(getattr(viewer.image_display_area, "_view_mode", "free") or "free")
            if vm in ("fit", "fit_width", "fit_height"):
                viewer.image_display_area.apply_current_view_mode()
        except Exception:
            pass
        try:
            if item_anchor_point is not None and getattr(viewer.image_display_area, "_pix_item", None):
                new_scene_point = viewer.image_display_area._pix_item.mapToScene(item_anchor_point)
                viewer.image_display_area.centerOn(new_scene_point)
        except Exception:
            pass
        # 좌표/상태 갱신: 현재 커서 위치 기준으로 동기화
        try:
            from PyQt6.QtCore import QPointF  # type: ignore[import]
            from PyQt6.QtGui import QCursor  # type: ignore[import]
            vp_point = viewer.image_display_area.viewport().mapFromGlobal(QCursor.pos())
            viewer.image_display_area._emit_cursor_pos_at_viewport_point(QPointF(vp_point))
        except Exception:
            pass
        try:
            viewer.update_status_right()
        except Exception:
            pass
        try:
            viewer.update_status_left()
        except Exception:
            pass
        # 한 틱 동안 깜빡임 방지 플래그
        try:
            from PyQt6.QtCore import QTimer  # type: ignore[import]
            viewer._just_upgraded_fullres = True
            QTimer.singleShot(0, lambda: setattr(viewer, "_just_upgraded_fullres", False))
        except Exception:
            pass
        # 업그레이드 완료: 플래그 해제
        try:
            viewer._is_scaled_preview = False
        except Exception:
            pass
    except Exception:
        pass


