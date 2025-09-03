from __future__ import annotations

from typing import TYPE_CHECKING
from PyQt6.QtGui import QMovie, QPixmap  # type: ignore[import]
from PyQt6.QtGui import QColorSpace  # type: ignore[import]

if TYPE_CHECKING:
    from .main_window import JusawiViewer


def is_current_file_animation(viewer: "JusawiViewer") -> bool:
    try:
        if not viewer.current_image_path:
            return False
        is_anim, _ = viewer.image_service.probe_animation(viewer.current_image_path)
        return bool(is_anim)
    except Exception:
        return False


def prev_frame(viewer: "JusawiViewer") -> None:
    if not is_current_file_animation(viewer):
        return
    try:
        cur = getattr(viewer.image_display_area, "_current_frame_index", 0)
        total = getattr(viewer.image_display_area, "_total_frames", -1)
        new_index = max(0, cur - 1)
        img, ok, err = viewer.image_service.load_frame(viewer.current_image_path, new_index)
        if ok and img and not img.isNull():
            viewer.image_display_area.setPixmap(QPixmap.fromImage(img))
            viewer.image_display_area.set_animation_state(True, new_index, total)
    except Exception:
        pass


def next_frame(viewer: "JusawiViewer") -> None:
    if not is_current_file_animation(viewer):
        return
    try:
        cur = getattr(viewer.image_display_area, "_current_frame_index", 0)
        total = getattr(viewer.image_display_area, "_total_frames", -1)
        max_index = (total - 1) if isinstance(total, int) and total > 0 else (cur + 1)
        new_index = min(max_index, cur + 1)
        img, ok, err = viewer.image_service.load_frame(viewer.current_image_path, new_index)
        if ok and img and not img.isNull():
            viewer.image_display_area.setPixmap(QPixmap.fromImage(img))
            viewer.image_display_area.set_animation_state(True, new_index, total)
    except Exception:
        pass


def toggle_play(viewer: "JusawiViewer") -> None:
    if not is_current_file_animation(viewer):
        return
    try:
        if viewer._movie:
            if viewer._movie.state() == QMovie.MovieState.Running:
                viewer._movie.setPaused(True)
                viewer._anim_is_playing = False
            elif viewer._movie.state() == QMovie.MovieState.Paused:
                viewer._movie.setPaused(False)
                viewer._anim_is_playing = True
            else:
                viewer._movie.start()
                viewer._anim_is_playing = True
        else:
            viewer._anim_is_playing = not viewer._anim_is_playing
            if viewer._anim_is_playing:
                viewer._anim_timer.start()
            else:
                viewer._anim_timer.stop()
    except Exception:
        pass


def on_tick(viewer: "JusawiViewer") -> None:
    if getattr(viewer, "_movie", None):
        return
    if not is_current_file_animation(viewer):
        viewer._anim_timer.stop()
        viewer._anim_is_playing = False
        return
    try:
        cur = getattr(viewer.image_display_area, "_current_frame_index", 0)
        total = getattr(viewer.image_display_area, "_total_frames", -1)
        if isinstance(total, int) and total > 1:
            next_index = (cur + 1) % total
        else:
            next_index = cur + 1
        img, ok, err = viewer.image_service.load_frame(viewer.current_image_path, next_index)
        if ok and img and not img.isNull():
            viewer.image_display_area.updatePixmapFrame(QPixmap.fromImage(img))
            if not (isinstance(total, int) and total > 0):
                try:
                    is_anim, fc = viewer.image_service.probe_animation(viewer.current_image_path)
                    total = fc if (is_anim and isinstance(fc, int)) else -1
                except Exception:
                    total = -1
            viewer.image_display_area.set_animation_state(True, next_index, total)
    except Exception:
        pass


def on_movie_frame(viewer: "JusawiViewer", frame_index: int) -> None:
    try:
        if not viewer._movie:
            return
        pm = viewer._movie.currentPixmap()
        if pm and not pm.isNull():
            if getattr(viewer, "_convert_movie_frames_to_srgb", False):
                try:
                    img = pm.toImage()
                    cs = img.colorSpace()
                    srgb = QColorSpace(QColorSpace.NamedColorSpace.SRgb)
                    if cs.isValid() and cs != srgb:
                        img.convertToColorSpace(srgb)
                    pm = QPixmap.fromImage(img)
                except Exception:
                    pass
            viewer.image_display_area.updatePixmapFrame(pm)
            total = viewer._movie.frameCount()
            viewer.image_display_area.set_animation_state(True, frame_index, total)
    except Exception:
        pass


