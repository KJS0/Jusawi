from __future__ import annotations


def set_global_shortcuts_enabled(viewer, enabled: bool) -> None:
    viewer._global_shortcuts_enabled = bool(enabled)
    try:
        for sc in getattr(viewer, "_shortcuts", []) or []:
            try:
                sc.setEnabled(viewer._global_shortcuts_enabled)
            except Exception:
                pass
    except Exception:
        pass
    try:
        if hasattr(viewer, "anim_space_shortcut") and viewer.anim_space_shortcut:
            viewer.anim_space_shortcut.setEnabled(viewer._global_shortcuts_enabled)
    except Exception:
        pass


