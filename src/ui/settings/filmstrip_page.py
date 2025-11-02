from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QComboBox, QSpinBox, QFormLayout,
    QLineEdit
)

from .base import SettingsPage


class FilmstripSettingsPage(SettingsPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(8)
        except Exception:
            pass

        # 크기/스크롤 섹션
        root.addWidget(QLabel("크기/스크롤", self))
        self.combo_scroll_mode = QComboBox(self)
        self.combo_scroll_mode.addItems(["항상 중앙", "가까운 쪽", "끄기"])  # always/nearest/off
        self.spin_default_size_idx = QSpinBox(self); self.spin_default_size_idx.setRange(0, 3); self.spin_default_size_idx.setSuffix(" idx")
        self.chk_remember_last_size = QCheckBox("마지막 썸네일 크기 자동 저장", self)
        self.spin_max_height_cap = QSpinBox(self); self.spin_max_height_cap.setRange(0, 2000); self.spin_max_height_cap.setSuffix(" px")
        form_size = QFormLayout()
        form_size.addRow("자동 스크롤", self.combo_scroll_mode)
        form_size.addRow("기본 크기 단계", self.spin_default_size_idx)
        form_size.addRow("마지막 크기 저장", self.chk_remember_last_size)
        form_size.addRow("최대 높이 상한", self.spin_max_height_cap)
        root.addLayout(form_size)

        # 여백/표시 섹션
        root.addWidget(QLabel("여백/표시", self))
        self.spin_h_margin = QSpinBox(self); self.spin_h_margin.setRange(0, 64); self.spin_h_margin.setSuffix(" px")
        self.spin_v_margin = QSpinBox(self); self.spin_v_margin.setRange(0, 64); self.spin_v_margin.setSuffix(" px")
        self.spin_border_thickness = QSpinBox(self); self.spin_border_thickness.setRange(1, 12); self.spin_border_thickness.setSuffix(" px")
        self.ed_border_color = QLineEdit(self); self.ed_border_color.setPlaceholderText("#RRGGBB")
        self.chk_show_separator = QCheckBox("항목 구분선 표시", self)
        form_style = QFormLayout()
        form_style.addRow("좌우 여백", self.spin_h_margin)
        form_style.addRow("상하 여백", self.spin_v_margin)
        form_style.addRow("선택 테두리 두께", self.spin_border_thickness)
        form_style.addRow("선택 테두리 색상", self.ed_border_color)
        form_style.addRow("구분선 표시", self.chk_show_separator)
        root.addLayout(form_style)

        # 툴팁 구성
        root.addWidget(QLabel("툴팁", self))
        self.chk_tt_name = QCheckBox("파일명", self)
        self.chk_tt_res = QCheckBox("해상도", self)
        self.chk_tt_rating = QCheckBox("평점", self)
        form_tt = QFormLayout()
        form_tt.addRow("파일명", self.chk_tt_name)
        form_tt.addRow("해상도", self.chk_tt_res)
        form_tt.addRow("평점", self.chk_tt_rating)
        root.addLayout(form_tt)

    def load_from_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            mode = str(getattr(viewer, "_filmstrip_scroll_mode", "always"))
            self.combo_scroll_mode.setCurrentIndex({"always":0, "nearest":1, "off":2}.get(mode, 0))
        except Exception:
            self.combo_scroll_mode.setCurrentIndex(0)
        try:
            self.spin_default_size_idx.setValue(int(getattr(viewer, "_filmstrip_default_size_idx", 3)))
        except Exception:
            self.spin_default_size_idx.setValue(3)
        try:
            self.chk_remember_last_size.setChecked(bool(getattr(viewer, "_filmstrip_remember_last_size", True)))
        except Exception:
            self.chk_remember_last_size.setChecked(True)
        try:
            self.spin_max_height_cap.setValue(int(getattr(viewer, "_filmstrip_max_height_cap", 0)))
        except Exception:
            self.spin_max_height_cap.setValue(0)
        try:
            self.spin_h_margin.setValue(int(getattr(viewer, "_filmstrip_item_h_margin", 12)))
        except Exception:
            self.spin_h_margin.setValue(12)
        try:
            self.spin_v_margin.setValue(int(getattr(viewer, "_filmstrip_item_v_margin", 14)))
        except Exception:
            self.spin_v_margin.setValue(14)
        try:
            self.spin_border_thickness.setValue(int(getattr(viewer, "_filmstrip_border_thickness", 3)))
        except Exception:
            self.spin_border_thickness.setValue(3)
        try:
            self.ed_border_color.setText(str(getattr(viewer, "_filmstrip_border_color", "#4DA3FF")) or "#4DA3FF")
        except Exception:
            self.ed_border_color.setText("#4DA3FF")
        try:
            self.chk_show_separator.setChecked(bool(getattr(viewer, "_filmstrip_show_separator", True)))
        except Exception:
            self.chk_show_separator.setChecked(True)
        try:
            self.chk_tt_name.setChecked(bool(getattr(viewer, "_filmstrip_tt_name", True)))
        except Exception:
            self.chk_tt_name.setChecked(True)
        try:
            self.chk_tt_res.setChecked(bool(getattr(viewer, "_filmstrip_tt_res", False)))
        except Exception:
            self.chk_tt_res.setChecked(False)
        try:
            self.chk_tt_rating.setChecked(bool(getattr(viewer, "_filmstrip_tt_rating", False)))
        except Exception:
            self.chk_tt_rating.setChecked(False)

    def apply_to_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            idx = int(self.combo_scroll_mode.currentIndex())
            viewer._filmstrip_scroll_mode = ("always" if idx == 0 else ("nearest" if idx == 1 else "off"))
        except Exception:
            pass
        try:
            viewer._filmstrip_default_size_idx = int(self.spin_default_size_idx.value())
        except Exception:
            pass
        try:
            viewer._filmstrip_remember_last_size = bool(self.chk_remember_last_size.isChecked())
        except Exception:
            pass
        try:
            viewer._filmstrip_max_height_cap = int(self.spin_max_height_cap.value())
        except Exception:
            pass
        try:
            viewer._filmstrip_item_h_margin = int(self.spin_h_margin.value())
            viewer._filmstrip_item_v_margin = int(self.spin_v_margin.value())
        except Exception:
            pass
        try:
            viewer._filmstrip_border_thickness = int(self.spin_border_thickness.value())
        except Exception:
            pass
        try:
            viewer._filmstrip_border_color = str(self.ed_border_color.text()).strip() or "#4DA3FF"
        except Exception:
            pass
        try:
            viewer._filmstrip_show_separator = bool(self.chk_show_separator.isChecked())
        except Exception:
            pass
        try:
            viewer._filmstrip_tt_name = bool(self.chk_tt_name.isChecked())
            viewer._filmstrip_tt_res = bool(self.chk_tt_res.isChecked())
            viewer._filmstrip_tt_rating = bool(self.chk_tt_rating.isChecked())
        except Exception:
            pass

    def reset_to_defaults(self) -> None:
        try:
            self.combo_scroll_mode.setCurrentIndex(0)
            self.spin_default_size_idx.setValue(3)
            self.chk_remember_last_size.setChecked(True)
            self.spin_max_height_cap.setValue(0)
            self.spin_h_margin.setValue(12)
            self.spin_v_margin.setValue(14)
            self.spin_border_thickness.setValue(3)
            self.ed_border_color.setText("#4DA3FF")
            self.chk_show_separator.setChecked(True)
            self.chk_tt_name.setChecked(True)
            self.chk_tt_res.setChecked(False)
            self.chk_tt_rating.setChecked(False)
        except Exception:
            pass


