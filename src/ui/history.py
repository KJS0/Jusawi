from __future__ import annotations

from typing import TYPE_CHECKING
from .state import TransformState

if TYPE_CHECKING:
    from .main_window import JusawiViewer


def capture_state(viewer: "JusawiViewer") -> TransformState:
    return TransformState(int(getattr(viewer, "_tf_rotation", 0)) % 360,
                          bool(getattr(viewer, "_tf_flip_h", False)),
                          bool(getattr(viewer, "_tf_flip_v", False))).normalized()


def restore_state(viewer: "JusawiViewer", state) -> None:
    try:
        if isinstance(state, TransformState):
            ts = state.normalized()
            viewer._tf_rotation = int(ts.rotation_degrees) % 360
            viewer._tf_flip_h = bool(ts.flip_horizontal)
            viewer._tf_flip_v = bool(ts.flip_vertical)
        else:
            rot, fh, fv = state
            viewer._tf_rotation = int(rot) % 360
            viewer._tf_flip_h = bool(fh)
            viewer._tf_flip_v = bool(fv)
        viewer._apply_transform_to_view()
        viewer._mark_dirty(True)
        if getattr(viewer.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
            viewer.image_display_area.apply_current_view_mode()
    except Exception:
        pass


def history_push(viewer: "JusawiViewer") -> None:
    try:
        viewer._history_undo.append(capture_state(viewer))
        viewer._history_redo.clear()
    except Exception:
        pass


def undo(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    if not getattr(viewer, "_history_undo", []):
        return
    try:
        cur = capture_state(viewer)
        prev = viewer._history_undo.pop()
        viewer._history_redo.append(cur)
        restore_state(viewer, prev)
    except Exception:
        pass


def redo(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "load_successful", False):
        return
    if not getattr(viewer, "_history_redo", []):
        return
    try:
        cur = capture_state(viewer)
        nxt = viewer._history_redo.pop()
        viewer._history_undo.append(cur)
        restore_state(viewer, nxt)
    except Exception:
        pass


