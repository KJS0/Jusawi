from __future__ import annotations

from PyQt6.QtCore import QDateTime  # type: ignore[import]


def maybe_gesture_nav(viewer, wheel_event) -> bool:
    """트랙패드 두 손가락 좌우 스와이프를 이전/다음 파일로 매핑."""
    try:
        cur_mode = str(getattr(viewer.image_display_area, "_view_mode", 'fit'))
        cur_scale = float(getattr(viewer.image_display_area, "_current_scale", 1.0) or 1.0)
        if not bool(getattr(viewer, "_gesture_nav_enabled", True)):
            return False
        if cur_mode not in ('fit', 'fit_width', 'fit_height') and cur_scale > 1.0001:
            return False
        try:
            dx = int(getattr(wheel_event.angleDelta(), 'x')())
        except Exception:
            dx = wheel_event.angleDelta().x()
        if abs(dx) < 1:
            return False
        now_ms = int(QDateTime.currentMSecsSinceEpoch())
        cd = int(getattr(viewer, "_gesture_nav_cooldown_ms", 300))
        if now_ms - int(getattr(viewer, "_gesture_last_trigger_ms", 0)) < cd:
            return False
        viewer._gesture_accum_x += dx
        thr = int(getattr(viewer, "_gesture_nav_threshold", 240))
        if viewer._gesture_accum_x <= -thr:
            viewer._gesture_last_trigger_ms = now_ms
            viewer._gesture_accum_x = 0
            try:
                viewer.show_next_image()
            except Exception:
                pass
            return True
        if viewer._gesture_accum_x >= thr:
            viewer._gesture_last_trigger_ms = now_ms
            viewer._gesture_accum_x = 0
            try:
                viewer.show_prev_image()
            except Exception:
                pass
            return True
        return False
    except Exception:
        return False


