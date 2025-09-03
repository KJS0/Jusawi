from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import JusawiViewer


def open_settings_dialog(viewer: "JusawiViewer") -> None:
    if hasattr(viewer, "_settings_dialog") and viewer._settings_dialog and viewer._settings_dialog.isVisible():
        try:
            viewer._settings_dialog.raise_()
            viewer._settings_dialog.activateWindow()
            try:
                viewer._settings_dialog.focus_shortcuts_tab()
            except Exception:
                pass
            return
        except Exception:
            pass
    viewer._set_global_shortcuts_enabled(False)
    dlg = viewer.__class__.__dict__.get('SettingsDialog', None)
    if dlg is None:
        from .settings_dialog import SettingsDialog  # late import
    SettingsDialog = locals().get('SettingsDialog')
    d = SettingsDialog(viewer)
    viewer._settings_dialog = d
    d.load_from_viewer(viewer)
    if d.exec() == d.DialogCode.Accepted:
        d.apply_to_viewer(viewer)
        try:
            viewer._apply_ui_theme_and_spacing()
        except Exception:
            pass
        viewer._preferred_view_mode = getattr(viewer, "_default_view_mode", 'fit')
        try:
            from ..shortcuts.shortcuts_manager import apply_shortcuts as apply_shortcuts_ext
            apply_shortcuts_ext(viewer)
        except Exception:
            pass
        viewer.save_settings()
    try:
        viewer._settings_dialog = None
    except Exception:
        pass
    viewer._set_global_shortcuts_enabled(True)


def open_shortcuts_help(viewer: "JusawiViewer") -> None:
    viewer._set_global_shortcuts_enabled(False)
    from .shortcuts_help_dialog import ShortcutsHelpDialog
    dlg = ShortcutsHelpDialog(viewer)
    dlg.exec()
    viewer._set_global_shortcuts_enabled(True)


