from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QComboBox, QSpinBox, QFormLayout,
)

from .base import SettingsPage


class FullscreenSettingsPage(SettingsPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(8)
        except Exception:
            pass

        self.spin_fs_auto_hide = QSpinBox(self); self.spin_fs_auto_hide.setRange(0, 10000); self.spin_fs_auto_hide.setSuffix(" ms")
        self.spin_cursor_hide = QSpinBox(self); self.spin_cursor_hide.setRange(0, 10000); self.spin_cursor_hide.setSuffix(" ms")
        self.combo_fs_viewmode = QComboBox(self); self.combo_fs_viewmode.addItems(["유지", "화면 맞춤", "가로 맞춤", "세로 맞춤", "실제 크기"])
        self.chk_fs_show_filmstrip = QCheckBox("전체화면에서 필름스트립 오버레이 표시", self)
        self.chk_fs_safe_exit = QCheckBox("Esc 안전 종료(1단계: UI 표시, 2단계: 종료)", self)
        self.chk_overlay_default = QCheckBox("앱 시작 시 정보 오버레이 표시", self)

        fs_form = QFormLayout()
        fs_form.addRow("UI 자동 숨김 지연", self.spin_fs_auto_hide)
        fs_form.addRow("커서 자동 숨김 지연", self.spin_cursor_hide)
        fs_form.addRow("진입 시 보기 모드", self.combo_fs_viewmode)
        fs_form.addRow("필름스트립 오버레이", self.chk_fs_show_filmstrip)
        fs_form.addRow("안전 종료 규칙", self.chk_fs_safe_exit)
        fs_form.addRow("정보 오버레이 기본 표시", self.chk_overlay_default)
        root.addLayout(fs_form)

    def load_from_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            self.spin_fs_auto_hide.setValue(int(getattr(viewer, "_fs_auto_hide_ms", 1500)))
        except Exception:
            self.spin_fs_auto_hide.setValue(1500)
        try:
            self.spin_cursor_hide.setValue(int(getattr(viewer, "_fs_auto_hide_cursor_ms", 1200)))
        except Exception:
            self.spin_cursor_hide.setValue(1200)
        try:
            mode = str(getattr(viewer, "_fs_enter_view_mode", "keep"))
            self.combo_fs_viewmode.setCurrentIndex({"keep":0, "fit":1, "fit_width":2, "fit_height":3, "actual":4}.get(mode, 0))
        except Exception:
            self.combo_fs_viewmode.setCurrentIndex(0)
        try:
            self.chk_fs_show_filmstrip.setChecked(bool(getattr(viewer, "_fs_show_filmstrip_overlay", False)))
        except Exception:
            self.chk_fs_show_filmstrip.setChecked(False)
        try:
            self.chk_fs_safe_exit.setChecked(bool(getattr(viewer, "_fs_safe_exit", True)))
        except Exception:
            self.chk_fs_safe_exit.setChecked(True)
        try:
            self.chk_overlay_default.setChecked(bool(getattr(viewer, "_overlay_enabled_default", False)))
        except Exception:
            self.chk_overlay_default.setChecked(False)

    def apply_to_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            viewer._fs_auto_hide_ms = int(self.spin_fs_auto_hide.value())
        except Exception:
            pass
        try:
            viewer._fs_auto_hide_cursor_ms = int(self.spin_cursor_hide.value())
        except Exception:
            pass
        try:
            idx = int(self.combo_fs_viewmode.currentIndex())
            viewer._fs_enter_view_mode = ("keep" if idx == 0 else ("fit" if idx == 1 else ("fit_width" if idx == 2 else ("fit_height" if idx == 3 else "actual"))))
        except Exception:
            pass
        try:
            viewer._fs_show_filmstrip_overlay = bool(self.chk_fs_show_filmstrip.isChecked())
        except Exception:
            pass
        try:
            viewer._fs_safe_exit = bool(self.chk_fs_safe_exit.isChecked())
        except Exception:
            pass
        try:
            viewer._overlay_enabled_default = bool(self.chk_overlay_default.isChecked())
        except Exception:
            pass

    def reset_to_defaults(self) -> None:
        try:
            self.spin_fs_auto_hide.setValue(1500)
            self.spin_cursor_hide.setValue(1200)
            self.combo_fs_viewmode.setCurrentIndex(0)
            self.chk_fs_show_filmstrip.setChecked(False)
            self.chk_fs_safe_exit.setChecked(True)
            self.chk_overlay_default.setChecked(False)
        except Exception:
            pass


