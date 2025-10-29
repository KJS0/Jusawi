from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QComboBox, QFormLayout,
)

from .base import SettingsPage


class ColorSettingsPage(SettingsPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(8)
        except Exception:
            pass

        self.chk_icc_ignore = QCheckBox("임베디드 ICC 무시", self)
        self.combo_assumed = QComboBox(self)
        self.combo_assumed.addItems(["sRGB", "Display P3", "Adobe RGB"])  # ICC 미탑재/무시 시 가정
        self.combo_target = QComboBox(self)
        self.combo_target.addItems(["sRGB", "Display P3", "Adobe RGB"])   # 미리보기 타깃
        self.combo_fallback = QComboBox(self)
        self.combo_fallback.addItems(["ignore", "force_sRGB"])  # 경고 UI는 보류
        self.chk_anim_convert = QCheckBox("애니메이션 프레임 sRGB 변환", self)
        self.chk_thumb_convert = QCheckBox("썸네일 sRGB 변환", self)

        form_color = QFormLayout()
        form_color.addRow("ICC 무시", self.chk_icc_ignore)
        form_color.addRow("ICC 없음 가정 색공간", self.combo_assumed)
        form_color.addRow("미리보기 타깃", self.combo_target)
        form_color.addRow("실패 시 폴백", self.combo_fallback)
        form_color.addRow("애니메이션 변환", self.chk_anim_convert)
        form_color.addRow("썸네일 변환", self.chk_thumb_convert)
        root.addLayout(form_color)

    def load_from_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            self.chk_icc_ignore.setChecked(bool(getattr(viewer, "_icc_ignore_embedded", False)))
        except Exception:
            self.chk_icc_ignore.setChecked(False)
        try:
            assumed = str(getattr(viewer, "_assumed_colorspace", "sRGB"))
            self.combo_assumed.setCurrentIndex({"sRGB":0, "Display P3":1, "Adobe RGB":2}.get(assumed, 0))
        except Exception:
            self.combo_assumed.setCurrentIndex(0)
        try:
            target = str(getattr(viewer, "_preview_target", "sRGB"))
            self.combo_target.setCurrentIndex({"sRGB":0, "Display P3":1, "Adobe RGB":2}.get(target, 0))
        except Exception:
            self.combo_target.setCurrentIndex(0)
        try:
            fb = str(getattr(viewer, "_fallback_policy", "ignore"))
            self.combo_fallback.setCurrentIndex({"ignore":0, "force_sRGB":1}.get(fb, 0))
        except Exception:
            self.combo_fallback.setCurrentIndex(0)
        try:
            self.chk_anim_convert.setChecked(bool(getattr(viewer, "_convert_movie_frames_to_srgb", True)))
        except Exception:
            self.chk_anim_convert.setChecked(True)
        try:
            self.chk_thumb_convert.setChecked(bool(getattr(viewer, "_thumb_convert_to_srgb", True)))
        except Exception:
            self.chk_thumb_convert.setChecked(True)

    def apply_to_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            viewer._icc_ignore_embedded = bool(self.chk_icc_ignore.isChecked())
        except Exception:
            pass
        try:
            idx = int(self.combo_assumed.currentIndex())
            viewer._assumed_colorspace = ("sRGB" if idx == 0 else ("Display P3" if idx == 1 else "Adobe RGB"))
        except Exception:
            pass
        try:
            idx = int(self.combo_target.currentIndex())
            viewer._preview_target = ("sRGB" if idx == 0 else ("Display P3" if idx == 1 else "Adobe RGB"))
        except Exception:
            pass
        try:
            viewer._fallback_policy = ("ignore" if int(self.combo_fallback.currentIndex()) == 0 else "force_sRGB")
        except Exception:
            pass
        try:
            viewer._convert_movie_frames_to_srgb = bool(self.chk_anim_convert.isChecked())
        except Exception:
            pass
        try:
            viewer._thumb_convert_to_srgb = bool(self.chk_thumb_convert.isChecked())
        except Exception:
            pass


