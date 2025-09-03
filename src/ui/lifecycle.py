from __future__ import annotations

from PyQt6.QtCore import QEvent  # type: ignore[import]

from . import display_scaling as ds


def on_show(viewer, event) -> None:
    try:
        viewer._ensure_screen_signal_connected()
    except Exception:
        pass


def before_event(viewer, e) -> bool:
    t = e.type()
    if t == QEvent.Type.DevicePixelRatioChange:
        viewer._begin_dpr_transition()
        try:
            ds.apply_scaled_pixmap_now(viewer)
        except Exception:
            pass
        vm = str(getattr(viewer.image_display_area, "_view_mode", "free") or "free")
        if vm in ("fit", "fit_width", "fit_height"):
            try:
                viewer.image_display_area.apply_current_view_mode()
            except Exception:
                pass
        return True
    return False


def on_close(viewer) -> None:
    try:
        viewer.log.info("window_close")
    except Exception:
        pass
    try:
        viewer.save_last_session()
    except Exception:
        pass


