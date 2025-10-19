from __future__ import annotations


def apply_ui_theme_and_spacing(viewer) -> None:
    try:
        m = getattr(viewer, "_ui_margins", (5, 5, 5, 5))
        viewer.main_layout.setContentsMargins(int(m[0]), int(m[1]), int(m[2]), int(m[3]))
        spacing = int(getattr(viewer, "_ui_spacing", 6))
        viewer.main_layout.setSpacing(spacing)
    except Exception:
        pass
    theme = getattr(viewer, "_theme", 'dark')
    resolved = theme
    if theme == 'system':
        try:
            import sys as _sys
            if _sys.platform == 'win32':
                try:
                    import winreg
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                        r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize") as k:
                        val, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
                        resolved = 'light' if int(val) == 1 else 'dark'
                except Exception:
                    resolved = 'dark'
            else:
                from PyQt6.QtWidgets import QApplication  # type: ignore[import]
                pal = QApplication.instance().palette() if QApplication.instance() else None
                if pal:
                    c = pal.window().color()
                    luma = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
                    resolved = 'light' if luma >= 127 else 'dark'
                else:
                    resolved = 'dark'
        except Exception:
            resolved = 'dark'
    try:
        viewer._resolved_theme = resolved
    except Exception:
        pass
    if resolved == 'light':
        bg = "#F0F0F0"
        fg = "#222222"
        bar_bg = "#E0E0E0"
    else:
        bg = "#373737"
        fg = "#EAEAEA"
        bar_bg = "#373737"
    try:
        viewer.centralWidget().setStyleSheet(f"background-color: {bg};")
    except Exception:
        pass
    try:
        button_style = f"color: {fg}; background-color: transparent;"
        for btn in [
            viewer.open_button,
            viewer.recent_button,
            getattr(viewer, 'info_button', None),
            viewer.fullscreen_button,
            viewer.prev_button,
            viewer.next_button,
            viewer.zoom_out_button,
            viewer.fit_button,
            viewer.zoom_in_button,
            viewer.rotate_left_button,
            viewer.rotate_right_button,
            viewer.settings_button,
            getattr(viewer, 'similar_button', None),
        ]:
            if btn:
                btn.setStyleSheet(button_style)
        # 다크 테마에서 AI 분석/검색은 흰색을 명시적으로 강제
        if resolved == 'dark':
            try:
                viewer.ai_button.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            except Exception:
                pass
            try:
                viewer.search_button.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            except Exception:
                pass
            try:
                if getattr(viewer, 'similar_button', None):
                    viewer.similar_button.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            except Exception:
                pass
        else:
            # 라이트 테마에서는 전체 버튼과 동일 색 적용
            try:
                viewer.ai_button.setStyleSheet(button_style)
            except Exception:
                pass
            try:
                viewer.search_button.setStyleSheet(button_style)
            except Exception:
                pass
            try:
                if getattr(viewer, 'similar_button', None):
                    viewer.similar_button.setStyleSheet(button_style)
            except Exception:
                pass
    except Exception:
        pass
    try:
        viewer.statusBar().setStyleSheet(
            f"QStatusBar {{ background-color: {bar_bg}; border-top: 1px solid {bar_bg}; color: {fg}; }} "
            f"QStatusBar QLabel {{ color: {fg}; }} "
            "QStatusBar::item { border: 0px; }"
        )
        viewer.status_left_label.setStyleSheet(f"color: {fg};")
        viewer.status_right_label.setStyleSheet(f"color: {fg};")
    except Exception:
        pass
    try:
        from PyQt6.QtGui import QColor, QBrush  # type: ignore[import]
        if resolved == 'light':
            viewer.image_display_area.setBackgroundBrush(QBrush(QColor("#F0F0F0")))
        else:
            viewer.image_display_area.setBackgroundBrush(QBrush(QColor("#373737")))
    except Exception:
        pass
    try:
        viewer.button_bar.setStyleSheet(f"background-color: transparent; QPushButton {{ color: {fg}; }}")
    except Exception:
        pass


