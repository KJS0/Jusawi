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
    # 단축키 탭을 즉시 초기화하여 기본 단축키가 표시되도록 강제
    try:
        d.focus_shortcuts_tab()
    except Exception:
        pass
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


# EXIF 열람 기능 제거됨


def open_ai_analysis_dialog(viewer: "JusawiViewer") -> None:
    if not getattr(viewer, "current_image_path", None):
        try:
            from PyQt6.QtWidgets import QMessageBox  # type: ignore[import]
            QMessageBox.information(viewer, "AI 분석", "먼저 사진을 열어주세요.")
        except Exception:
            pass
        return
    try:
        viewer._set_global_shortcuts_enabled(False)
    except Exception:
        pass
    try:
        from .ai_analysis_dialog import AIAnalysisDialog
        d = AIAnalysisDialog(viewer, image_path=viewer.current_image_path)
        d.resize(760, 600)
        d.exec()
    except Exception:
        pass
    finally:
        try:
            viewer._set_global_shortcuts_enabled(True)
        except Exception:
            pass


def open_natural_search_dialog(viewer: "JusawiViewer") -> None:
    files = getattr(viewer, "image_files_in_dir", []) or []
    if not files:
        try:
            import os  # lazy import inside function
            cur = getattr(viewer, "current_image_path", "") or ""
            if cur and os.path.exists(cur):
                dir_path = os.path.dirname(cur)
                if dir_path and os.path.isdir(dir_path):
                    viewer.scan_directory(dir_path)
                    files = getattr(viewer, "image_files_in_dir", []) or []
        except Exception:
            files = []
    if not files:
        from PyQt6.QtWidgets import QMessageBox  # type: ignore[import]
        QMessageBox.information(viewer, "자연어 검색", "현재 파일의 폴더를 확인할 수 없습니다.")
        return
    try:
        viewer._set_global_shortcuts_enabled(False)
    except Exception:
        pass
    try:
        from .natural_search_dialog import NaturalSearchDialog
        d = NaturalSearchDialog(viewer, files=files)
        d.resize(800, 600)
        d.exec()
    except Exception as e:
        try:
            from PyQt6.QtWidgets import QMessageBox  # type: ignore[import]
            QMessageBox.warning(viewer, "자연어 검색", f"다이얼로그 열기 실패: {e}")
        except Exception:
            pass
    finally:
        try:
            viewer._set_global_shortcuts_enabled(True)
        except Exception:
            pass


