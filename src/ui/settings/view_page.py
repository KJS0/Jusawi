from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QComboBox, QSpinBox, QFormLayout,
)

from .base import SettingsPage


class ViewSettingsPage(SettingsPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(8)
        except Exception:
            pass

        form_view = QFormLayout()
        self.combo_default_view = QComboBox(self)
        self.combo_default_view.addItems(["화면 맞춤", "가로 맞춤", "세로 맞춤", "실제 크기"])  # fit/fit_width/fit_height/actual
        from PyQt6.QtWidgets import QDoubleSpinBox as _DSpin, QSpinBox as _ISpin  # type: ignore
        self.spin_min_scale = _ISpin(self); self.spin_min_scale.setRange(1, 1600); self.spin_min_scale.setSuffix(" %")
        self.spin_max_scale = _ISpin(self); self.spin_max_scale.setRange(1, 6400); self.spin_max_scale.setSuffix(" %")
        self.chk_fixed_steps = QCheckBox("고정 줌 단계 사용", self)
        self.spin_zoom_step = _DSpin(self); self.spin_zoom_step.setRange(1.02, 2.5); self.spin_zoom_step.setSingleStep(0.01)
        self.spin_precise_step = _DSpin(self); self.spin_precise_step.setRange(1.01, 2.0); self.spin_precise_step.setSingleStep(0.01)
        self.chk_smooth = QCheckBox("고품질 보간(스무딩)", self)
        self.spin_fit_margin = QSpinBox(self); self.spin_fit_margin.setRange(0, 40); self.spin_fit_margin.setSuffix(" %")
        self.chk_wheel_requires_ctrl = QCheckBox("휠 줌에 Ctrl 필요", self)
        self.chk_alt_precise = QCheckBox("Alt+휠 정밀 줌 허용", self)
        self.combo_dbl = QComboBox(self); self.combo_dbl.addItems(["토글(화면↔100%)", "화면 맞춤", "가로 맞춤", "세로 맞춤", "실제 크기", "없음"])  # toggle/fit/fit_width/fit_height/actual/none
        self.combo_mid = QComboBox(self); self.combo_mid.addItems(["없음", "토글(화면↔100%)", "화면 맞춤", "실제 크기"])  # none/toggle/fit/actual
        self.chk_refit_on_tf = QCheckBox("회전/반전 후 자동 재맞춤", self)
        self.chk_anchor_preserve = QCheckBox("회전 시 화면 중심 앵커 유지", self)
        self.chk_preserve_visual_dpr = QCheckBox("DPR 변경 시 시각 크기 유지", self)

        form_view.addRow("기본 보기 모드", self.combo_default_view)
        form_view.addRow("최소 확대 비율", self.spin_min_scale)
        form_view.addRow("최대 확대 비율", self.spin_max_scale)
        form_view.addRow("고정 줌 단계", self.chk_fixed_steps)
        form_view.addRow("줌 단계", self.spin_zoom_step)
        form_view.addRow("미세 줌 단계", self.spin_precise_step)
        form_view.addRow("고품질 보간", self.chk_smooth)
        form_view.addRow("화면 맞춤 여백", self.spin_fit_margin)
        form_view.addRow("휠 Ctrl 필요", self.chk_wheel_requires_ctrl)
        form_view.addRow("Alt 정밀 줌", self.chk_alt_precise)
        form_view.addRow("더블클릭 동작", self.combo_dbl)
        form_view.addRow("휠클릭 동작", self.combo_mid)
        form_view.addRow("회전/반전 재맞춤", self.chk_refit_on_tf)
        form_view.addRow("회전 중심 앵커 유지", self.chk_anchor_preserve)
        form_view.addRow("DPR 시각 크기 유지", self.chk_preserve_visual_dpr)
        root.addLayout(form_view)

    def load_from_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            dvm = str(getattr(viewer, "_default_view_mode", 'fit'))
            self.combo_default_view.setCurrentIndex({"fit":0, "fit_width":1, "fit_height":2, "actual":3}.get(dvm, 0))
        except Exception:
            self.combo_default_view.setCurrentIndex(0)
        try:
            self.spin_min_scale.setValue(int(round(float(getattr(viewer, "min_scale", 0.01)) * 100)))
            self.spin_max_scale.setValue(int(round(float(getattr(viewer, "max_scale", 16.0)) * 100)))
        except Exception:
            self.spin_min_scale.setValue(1); self.spin_max_scale.setValue(1600)
        try:
            self.chk_fixed_steps.setChecked(bool(getattr(viewer, "_use_fixed_zoom_steps", False)))
        except Exception:
            self.chk_fixed_steps.setChecked(False)
        try:
            self.spin_zoom_step.setValue(float(getattr(viewer, "_zoom_step_factor", 1.25)))
            self.spin_precise_step.setValue(float(getattr(viewer, "_precise_zoom_step_factor", 1.1)))
        except Exception:
            self.spin_zoom_step.setValue(1.25); self.spin_precise_step.setValue(1.1)
        try:
            self.chk_smooth.setChecked(bool(getattr(viewer, "_smooth_transform", True)))
        except Exception:
            self.chk_smooth.setChecked(True)
        try:
            self.spin_fit_margin.setValue(int(getattr(viewer, "_fit_margin_pct", 0)))
        except Exception:
            self.spin_fit_margin.setValue(0)
        try:
            self.chk_wheel_requires_ctrl.setChecked(bool(getattr(viewer, "_wheel_zoom_requires_ctrl", True)))
        except Exception:
            self.chk_wheel_requires_ctrl.setChecked(True)
        try:
            self.chk_alt_precise.setChecked(bool(getattr(viewer, "_wheel_zoom_alt_precise", True)))
        except Exception:
            self.chk_alt_precise.setChecked(True)
        try:
            dbl = str(getattr(viewer, "_double_click_action", 'toggle'))
            self.combo_dbl.setCurrentIndex({"toggle":0, "fit":1, "fit_width":2, "fit_height":3, "actual":4, "none":5}.get(dbl, 0))
        except Exception:
            self.combo_dbl.setCurrentIndex(0)
        try:
            mid = str(getattr(viewer, "_middle_click_action", 'none'))
            self.combo_mid.setCurrentIndex({"none":0, "toggle":1, "fit":2, "actual":3}.get(mid, 0))
        except Exception:
            self.combo_mid.setCurrentIndex(0)
        try:
            self.chk_refit_on_tf.setChecked(bool(getattr(viewer, "_refit_on_transform", True)))
        except Exception:
            self.chk_refit_on_tf.setChecked(True)
        try:
            self.chk_anchor_preserve.setChecked(bool(getattr(viewer, "_anchor_preserve_on_transform", True)))
        except Exception:
            self.chk_anchor_preserve.setChecked(True)
        try:
            self.chk_preserve_visual_dpr.setChecked(bool(getattr(viewer, "_preserve_visual_size_on_dpr_change", False)))
        except Exception:
            self.chk_preserve_visual_dpr.setChecked(False)

    def apply_to_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            idx = int(self.combo_default_view.currentIndex())
            viewer._default_view_mode = ("fit" if idx == 0 else ("fit_width" if idx == 1 else ("fit_height" if idx == 2 else "actual")))
        except Exception:
            pass
        try:
            viewer.min_scale = float(int(self.spin_min_scale.value())) / 100.0
            viewer.max_scale = float(int(self.spin_max_scale.value())) / 100.0
            if hasattr(viewer, 'image_display_area'):
                viewer.image_display_area.set_min_max_scale(viewer.min_scale, viewer.max_scale)
        except Exception:
            pass
        try:
            viewer._use_fixed_zoom_steps = bool(self.chk_fixed_steps.isChecked())
            viewer._zoom_step_factor = float(self.spin_zoom_step.value())
            viewer._precise_zoom_step_factor = float(self.spin_precise_step.value())
        except Exception:
            pass
        try:
            viewer._smooth_transform = bool(self.chk_smooth.isChecked())
        except Exception:
            pass
        try:
            viewer._fit_margin_pct = int(self.spin_fit_margin.value())
        except Exception:
            pass
        try:
            viewer._wheel_zoom_requires_ctrl = bool(self.chk_wheel_requires_ctrl.isChecked())
        except Exception:
            pass
        try:
            viewer._wheel_zoom_alt_precise = bool(self.chk_alt_precise.isChecked())
        except Exception:
            pass
        try:
            viewer._double_click_action = ("toggle" if int(self.combo_dbl.currentIndex()) == 0 else ("fit" if int(self.combo_dbl.currentIndex()) == 1 else ("fit_width" if int(self.combo_dbl.currentIndex()) == 2 else ("fit_height" if int(self.combo_dbl.currentIndex()) == 3 else ("actual" if int(self.combo_dbl.currentIndex()) == 4 else "none")))))
        except Exception:
            pass
        try:
            viewer._middle_click_action = ("none" if int(self.combo_mid.currentIndex()) == 0 else ("toggle" if int(self.combo_mid.currentIndex()) == 1 else ("fit" if int(self.combo_mid.currentIndex()) == 2 else "actual")))
        except Exception:
            pass
        try:
            viewer._refit_on_transform = bool(self.chk_refit_on_tf.isChecked())
        except Exception:
            pass
        try:
            viewer._anchor_preserve_on_transform = bool(self.chk_anchor_preserve.isChecked())
        except Exception:
            pass
        try:
            viewer._preserve_visual_size_on_dpr_change = bool(self.chk_preserve_visual_dpr.isChecked())
        except Exception:
            pass

    def reset_to_defaults(self) -> None:
        try:
            self.combo_default_view.setCurrentIndex(0)
            self.spin_min_scale.setValue(1)
            self.spin_max_scale.setValue(1600)
            self.chk_fixed_steps.setChecked(False)
            self.spin_zoom_step.setValue(1.25)
            self.spin_precise_step.setValue(1.1)
            self.chk_smooth.setChecked(True)
            self.spin_fit_margin.setValue(0)
            self.chk_wheel_requires_ctrl.setChecked(True)
            self.chk_alt_precise.setChecked(True)
            self.combo_dbl.setCurrentIndex(0)
            self.combo_mid.setCurrentIndex(0)
            self.chk_refit_on_tf.setChecked(True)
            self.chk_anchor_preserve.setChecked(True)
            self.chk_preserve_visual_dpr.setChecked(False)
        except Exception:
            pass


