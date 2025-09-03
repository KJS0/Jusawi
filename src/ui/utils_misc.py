from __future__ import annotations


def clamp(value, min_v, max_v):
    return max(min_v, min(value, max_v))


def enable_dnd_on(widget, viewer) -> None:
    from ..dnd.dnd_setup import enable_dnd as enable_dnd_ext
    enable_dnd_ext(widget, viewer)


def setup_global_dnd(viewer) -> None:
    from ..dnd.dnd_setup import setup_global_dnd as setup_global_dnd_ext
    setup_global_dnd_ext(viewer)


def handle_escape(viewer) -> None:
    from PyQt6.QtWidgets import QApplication  # type: ignore[import]
    if viewer.is_slideshow_active:
        viewer.stop_slideshow()
    elif viewer.is_fullscreen:
        viewer.exit_fullscreen()
    else:
        QApplication.quit()


