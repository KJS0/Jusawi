from __future__ import annotations

def style_rating_bar(viewer) -> None:
    try:
        from . import rating_bar as _rating_bar
        _rating_bar.apply_theme(viewer, False)
    except Exception:
        pass


def apply_ui_theme_and_spacing(viewer) -> None:
    try:
        m = getattr(viewer, "_ui_margins", (5, 5, 5, 5))
        viewer.main_layout.setContentsMargins(int(m[0]), int(m[1]), int(m[2]), int(m[3]))
        spacing = int(getattr(viewer, "_ui_spacing", 6))
        viewer.main_layout.setSpacing(spacing)
    except Exception:
        pass
    # Light 테마 제거: 항상 다크 테마로 강제
    resolved = 'dark'
    try:
        viewer._resolved_theme = resolved
    except Exception:
        pass
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
        viewer.image_display_area.setBackgroundBrush(QBrush(QColor("#373737")))
    except Exception:
        pass
    try:
        viewer.button_bar.setStyleSheet(f"background-color: transparent; QPushButton {{ color: {fg}; }}")
    except Exception:
        pass

    # Info panel theming (dark only) + 동적 폰트 크기
    try:
        if getattr(viewer, 'info_text', None) is not None:
            try:
                total_w = max(640, int(viewer.width()))
                scaled = max(16, min(24, int(total_w / 80)))
            except Exception:
                scaled = 20
            viewer.info_text.setStyleSheet(
                f"QTextEdit {{ color: #EAEAEA; background-color: #2B2B2B; border: 1px solid #444; font-size: {scaled}px; line-height: 140%; }} QTextEdit:disabled {{ color: #777777; }}"
            )
    except Exception:
        pass
    try:
        if getattr(viewer, 'info_map_label', None) is not None:
            viewer.info_map_label.setStyleSheet("QLabel { background-color: #2B2B2B; color: #AAAAAA; border: 1px solid #444; }")
    except Exception:
        pass

    # Filmstrip theming (dark only, including scrollbar)
    try:
        fs = getattr(viewer, 'filmstrip', None)
        if fs is not None:
            fs.setStyleSheet(
                "QListView, QListView::viewport { background-color: #1F1F1F; }"
                " QScrollBar:horizontal { background: #2B2B2B; height: 12px; }"
                " QScrollBar::handle:horizontal { background: #555; min-width: 24px; border-radius: 6px; }"
                " QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { background: transparent; width: 0px; }"
                " QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: #2B2B2B; }"
            )
            try:
                from PyQt6.QtGui import QPalette, QColor  # type: ignore
                pal = fs.viewport().palette()
                pal.setColor(QPalette.ColorRole.Base, QColor("#1F1F1F"))
                pal.setColor(QPalette.ColorRole.Window, QColor("#1F1F1F"))
                fs.viewport().setPalette(pal)
                fs.viewport().setAutoFillBackground(True)
            except Exception:
                pass
    except Exception:
        pass

    # Rating bar theming centralized (base)
    try:
        style_rating_bar(viewer)
    except Exception:
        pass

    # Dialogs and common widgets theming (extend coverage)
    try:
        fg = fg  # already defined
        bg = bg
        # Apply to known dialogs if present
        for name in [
            'settings_dialog',
            'shortcuts_help_dialog',
            'ai_analysis_dialog',
            'natural_search_dialog',
            'similar_search_dialog',
        ]:
            dlg = getattr(viewer, name, None)
            if dlg is None:
                continue
            try:
                dlg.setStyleSheet(
                    f"QDialog {{ background-color: {bg}; color: {fg}; }}"
                    f" QLabel {{ color: {fg}; }}"
                    f" QLineEdit, QComboBox, QTextEdit {{ background-color: #2B2B2B; color: {fg}; border: 1px solid #444; }}"
                    f" QPushButton {{ color: {fg}; background-color: transparent; border: 1px solid {'#9E9E9E' if resolved=='light' else '#555'}; padding: 4px 8px; border-radius: 4px; }}"
                )
            except Exception:
                pass
    except Exception:
        pass


