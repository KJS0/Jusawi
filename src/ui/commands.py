from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import JusawiViewer


def fit_to_window(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer.image_display_area.fit_to_window()
    viewer.update_button_states()
    try:
        viewer._session_preferred_view_mode = 'fit'
    except Exception:
        pass


def fit_to_width(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer.image_display_area.fit_to_width()
    viewer.update_button_states()
    try:
        viewer._session_preferred_view_mode = 'fit_width'
    except Exception:
        pass


def fit_to_height(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer.image_display_area.fit_to_height()
    viewer.update_button_states()
    try:
        viewer._session_preferred_view_mode = 'fit_height'
    except Exception:
        pass


def zoom_in(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer.image_display_area.zoom_in()
    viewer.update_button_states()


def zoom_out(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer.image_display_area.zoom_out()
    viewer.update_button_states()


def reset_to_100(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer.fit_mode = False
    viewer.scale_factor = 1.0
    viewer.image_display_area.reset_to_100()
    viewer.update_button_states()
    viewer.update_status_right()
    try:
        viewer._session_preferred_view_mode = 'actual'
    except Exception:
        pass


def rotate_cw_90(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer._history_push()
    viewer._tf_rotation = (viewer._tf_rotation + 90) % 360
    viewer._apply_transform_to_view()
    viewer._mark_dirty(True)
    if bool(getattr(viewer, "_refit_on_transform", True)) and getattr(viewer.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
        viewer.image_display_area.apply_current_view_mode()


def rotate_ccw_90(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer._history_push()
    viewer._tf_rotation = (viewer._tf_rotation - 90) % 360
    viewer._apply_transform_to_view()
    viewer._mark_dirty(True)
    if bool(getattr(viewer, "_refit_on_transform", True)) and getattr(viewer.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
        viewer.image_display_area.apply_current_view_mode()


def rotate_180(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer._history_push()
    viewer._tf_rotation = (viewer._tf_rotation + 180) % 360
    viewer._apply_transform_to_view()
    viewer._mark_dirty(True)
    if bool(getattr(viewer, "_refit_on_transform", True)) and getattr(viewer.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
        viewer.image_display_area.apply_current_view_mode()


def rotate_cycle(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer._history_push()
    viewer._tf_rotation = (viewer._tf_rotation + 90) % 360
    viewer._apply_transform_to_view()
    viewer._mark_dirty(True)
    if bool(getattr(viewer, "_refit_on_transform", True)) and getattr(viewer.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
        viewer.image_display_area.apply_current_view_mode()


def flip_horizontal(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer._history_push()
    viewer._tf_flip_h = not bool(viewer._tf_flip_h)
    viewer._apply_transform_to_view()
    viewer._mark_dirty(True)
    if bool(getattr(viewer, "_refit_on_transform", True)) and getattr(viewer.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
        viewer.image_display_area.apply_current_view_mode()


def flip_vertical(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer._history_push()
    viewer._tf_flip_v = not bool(viewer._tf_flip_v)
    viewer._apply_transform_to_view()
    viewer._mark_dirty(True)
    if getattr(viewer.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
        viewer.image_display_area.apply_current_view_mode()


def reset_transform(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    viewer._history_push()
    viewer._tf_rotation = 0
    viewer._tf_flip_h = False
    viewer._tf_flip_v = False
    viewer._apply_transform_to_view()
    viewer._mark_dirty(True)
    if bool(getattr(viewer, "_refit_on_transform", True)) and getattr(viewer.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
        viewer.image_display_area.apply_current_view_mode()

