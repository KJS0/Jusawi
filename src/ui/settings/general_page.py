from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QComboBox, QSpinBox, QFormLayout,
)

from .base import SettingsPage


class GeneralSettingsPage(SettingsPage):
    """일반 탭 구현: 기존 SettingsDialog 일반 섹션을 모듈화.

    UI 요소 id/역할은 기존 다이얼로그 구현을 그대로 따릅니다.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(8)
        except Exception:
            pass

        # 파일 열기 관련
        self.chk_scan_after_open = QCheckBox("열기 후 폴더 자동 스캔", self)
        self.chk_remember_last_dir = QCheckBox("마지막 사용 폴더 기억", self)
        root.addWidget(self.chk_scan_after_open)
        root.addWidget(self.chk_remember_last_dir)

        # 세션/최근 옵션
        root.addWidget(QLabel("세션/최근", self))
        self.combo_startup_restore = QComboBox(self)
        self.combo_startup_restore.addItems(["항상 복원", "묻기", "복원 안 함"])  # always/ask/never
        self.spin_recent_max = QSpinBox(self); self.spin_recent_max.setRange(1, 100); self.spin_recent_max.setSuffix(" 개")
        self.chk_recent_auto_prune = QCheckBox("존재하지 않는 항목 자동 정리", self)
        form_recent = QFormLayout()
        form_recent.addRow("시작 시 세션 복원", self.combo_startup_restore)
        form_recent.addRow("최근 목록 최대 개수", self.spin_recent_max)
        form_recent.addRow("존재하지 않음 자동 정리", self.chk_recent_auto_prune)
        root.addLayout(form_recent)

        # 애니메이션
        root.addWidget(QLabel("애니메이션", self))
        self.chk_anim_autoplay = QCheckBox("자동 재생", self)
        self.chk_anim_loop = QCheckBox("루프 재생", self)
        self.chk_anim_keep_state = QCheckBox("파일 전환 시 재생 상태 유지", self)
        self.chk_anim_pause_unfocus = QCheckBox("비활성화 시 자동 일시정지", self)
        self.chk_anim_click_toggle = QCheckBox("이미지 클릭으로 재생/일시정지", self)
        self.chk_anim_overlay_enable = QCheckBox("프레임 오버레이 표시", self)
        self.chk_anim_overlay_show_index = QCheckBox("프레임 번호/총 프레임 표시", self)
        self.combo_anim_overlay_pos = QComboBox(self)
        self.combo_anim_overlay_pos.addItems(["좌상", "우상", "좌하", "우하"])  # top-left/right/bottom-left/right
        from PyQt6.QtWidgets import QDoubleSpinBox as _DSpin  # type: ignore
        self.spin_anim_overlay_opacity = _DSpin(self); self.spin_anim_overlay_opacity.setRange(0.05, 1.0); self.spin_anim_overlay_opacity.setSingleStep(0.05)
        form_anim = QFormLayout()
        form_anim.addRow("재생 상태 유지", self.chk_anim_keep_state)
        form_anim.addRow("비활성화 시 일시정지", self.chk_anim_pause_unfocus)
        form_anim.addRow("클릭으로 재생/일시정지", self.chk_anim_click_toggle)
        form_anim.addRow("오버레이 표시", self.chk_anim_overlay_enable)
        form_anim.addRow("프레임 텍스트", self.chk_anim_overlay_show_index)
        form_anim.addRow("오버레이 위치", self.combo_anim_overlay_pos)
        form_anim.addRow("오버레이 불투명도", self.spin_anim_overlay_opacity)
        root.addWidget(self.chk_anim_autoplay)
        root.addWidget(self.chk_anim_loop)
        root.addLayout(form_anim)

        # 디렉터리 탐색 정렬/필터
        root.addWidget(QLabel("디렉터리 탐색", self))
        self.combo_sort_mode = QComboBox(self)
        self.combo_sort_mode.addItems(["메타데이터/촬영시간", "파일명"])
        self.combo_sort_name = QComboBox(self)
        self.combo_sort_name.addItems(["윈도우 탐색기 정렬", "사전식 정렬"])
        self.chk_exclude_hidden = QCheckBox("숨김/시스템 파일 제외", self)
        self.chk_wrap_ends = QCheckBox("끝에서 반대쪽으로 순환 이동", self)
        self.spin_nav_throttle = QSpinBox(self); self.spin_nav_throttle.setRange(0, 2000); self.spin_nav_throttle.setSuffix(" ms")
        self.chk_film_center = QCheckBox("필름스트립 항목을 자동 중앙 정렬", self)
        self.combo_zoom_policy = QComboBox(self); self.combo_zoom_policy.addItems(["전환 시 초기화", "보기 모드 유지", "배율 유지"])
        form = QFormLayout()
        form.addRow("정렬 기준", self.combo_sort_mode)
        form.addRow("파일명 정렬", self.combo_sort_name)
        form.addRow("필터", self.chk_exclude_hidden)
        form.addRow("끝에서의 동작", self.chk_wrap_ends)
        form.addRow("연속 탐색 속도", self.spin_nav_throttle)
        form.addRow("필름스트립 중앙 정렬", self.chk_film_center)
        form.addRow("확대 상태 유지", self.combo_zoom_policy)
        root.addLayout(form)

        # 드래그 앤 드롭 옵션
        root.addWidget(QLabel("드래그 앤 드롭", self))
        self.chk_drop_allow_folder = QCheckBox("폴더 드롭 허용", self)
        self.chk_drop_parent_scan = QCheckBox("부모 폴더 스캔으로 전체 탐색", self)
        self.chk_drop_overlay = QCheckBox("대용량 드롭 진행 오버레이 표시", self)
        self.chk_drop_confirm = QCheckBox("파일 수 임계치 초과 시 확인창", self)
        self.spin_drop_threshold = QSpinBox(self); self.spin_drop_threshold.setRange(50, 100000); self.spin_drop_threshold.setSuffix(" 개")
        form_dnd = QFormLayout()
        form_dnd.addRow("폴더 드롭", self.chk_drop_allow_folder)
        form_dnd.addRow("목록 구성", self.chk_drop_parent_scan)
        form_dnd.addRow("진행 오버레이", self.chk_drop_overlay)
        form_dnd.addRow("대용량 확인", self.chk_drop_confirm)
        form_dnd.addRow("임계치", self.spin_drop_threshold)
        root.addLayout(form_dnd)

        # TIFF
        self.chk_tiff_first_page = QCheckBox("항상 첫 페이지로 열기", self)
        row_tiff = QFormLayout()
        row_tiff.addRow("TIFF", self.chk_tiff_first_page)
        root.addLayout(row_tiff)

    # 데이터 바인딩
    def load_from_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            self.chk_scan_after_open.setChecked(bool(getattr(viewer, "_open_scan_dir_after_open", True)))
        except Exception:
            self.chk_scan_after_open.setChecked(True)
        try:
            self.chk_remember_last_dir.setChecked(bool(getattr(viewer, "_remember_last_open_dir", True)))
        except Exception:
            self.chk_remember_last_dir.setChecked(True)
        try:
            self.chk_anim_autoplay.setChecked(bool(getattr(viewer, "_anim_autoplay", True)))
        except Exception:
            self.chk_anim_autoplay.setChecked(True)
        try:
            self.chk_anim_loop.setChecked(bool(getattr(viewer, "_anim_loop", True)))
        except Exception:
            self.chk_anim_loop.setChecked(True)
        try:
            self.chk_anim_keep_state.setChecked(bool(getattr(viewer, "_anim_keep_state_on_switch", False)))
        except Exception:
            self.chk_anim_keep_state.setChecked(False)
        try:
            self.chk_anim_pause_unfocus.setChecked(bool(getattr(viewer, "_anim_pause_on_unfocus", False)))
        except Exception:
            self.chk_anim_pause_unfocus.setChecked(False)
        try:
            self.chk_anim_click_toggle.setChecked(bool(getattr(viewer, "_anim_click_toggle", False)))
        except Exception:
            self.chk_anim_click_toggle.setChecked(False)
        try:
            self.chk_anim_overlay_enable.setChecked(bool(getattr(viewer, "_anim_overlay_enabled", False)))
        except Exception:
            self.chk_anim_overlay_enable.setChecked(False)
        try:
            self.chk_anim_overlay_show_index.setChecked(bool(getattr(viewer, "_anim_overlay_show_index", True)))
        except Exception:
            self.chk_anim_overlay_show_index.setChecked(True)
        try:
            pos = str(getattr(viewer, "_anim_overlay_position", "top-right"))
            self.combo_anim_overlay_pos.setCurrentIndex({"top-left":0, "top-right":1, "bottom-left":2, "bottom-right":3}.get(pos, 1))
        except Exception:
            self.combo_anim_overlay_pos.setCurrentIndex(1)
        try:
            self.spin_anim_overlay_opacity.setValue(float(getattr(viewer, "_anim_overlay_opacity", 0.6)))
        except Exception:
            from PyQt6.QtWidgets import QDoubleSpinBox as _DSpin  # type: ignore
            self.spin_anim_overlay_opacity.setValue(0.6)  # type: ignore[arg-type]
        # 세션/최근
        try:
            pol = str(getattr(viewer, "_startup_restore_policy", "always"))
            self.combo_startup_restore.setCurrentIndex({"always":0, "ask":1, "never":2}.get(pol, 0))
        except Exception:
            self.combo_startup_restore.setCurrentIndex(0)
        try:
            self.spin_recent_max.setValue(int(getattr(viewer, "_recent_max_items", 10)))
        except Exception:
            self.spin_recent_max.setValue(10)
        try:
            self.chk_recent_auto_prune.setChecked(bool(getattr(viewer, "_recent_auto_prune_missing", True)))
        except Exception:
            self.chk_recent_auto_prune.setChecked(True)
        # 정렬/필터
        try:
            mode = str(getattr(viewer, "_dir_sort_mode", "metadata"))
            self.combo_sort_mode.setCurrentIndex(0 if mode == "metadata" else 1)
        except Exception:
            self.combo_sort_mode.setCurrentIndex(0)
        try:
            self.combo_sort_name.setCurrentIndex(0 if bool(getattr(viewer, "_dir_natural_sort", True)) else 1)
        except Exception:
            self.combo_sort_name.setCurrentIndex(0)
        try:
            self.combo_sort_mode.setEnabled(self.combo_sort_name.currentIndex() != 0)
        except Exception:
            pass
        try:
            self.chk_exclude_hidden.setChecked(bool(getattr(viewer, "_dir_exclude_hidden_system", True)))
        except Exception:
            self.chk_exclude_hidden.setChecked(True)
        try:
            self.chk_tiff_first_page.setChecked(bool(getattr(viewer, "_tiff_open_first_page_only", True)))
        except Exception:
            self.chk_tiff_first_page.setChecked(True)
        # 추가 옵션
        try:
            self.chk_wrap_ends.setChecked(bool(getattr(viewer, "_nav_wrap_ends", False)))
        except Exception:
            self.chk_wrap_ends.setChecked(False)
        try:
            self.spin_nav_throttle.setValue(int(getattr(viewer, "_nav_min_interval_ms", 100)))
        except Exception:
            self.spin_nav_throttle.setValue(100)
        try:
            self.chk_film_center.setChecked(bool(getattr(viewer, "_filmstrip_auto_center", True)))
        except Exception:
            self.chk_film_center.setChecked(True)
        try:
            zp = str(getattr(viewer, "_zoom_policy", "mode"))
            self.combo_zoom_policy.setCurrentIndex({"reset":0, "mode":1, "scale":2}.get(zp, 1))
        except Exception:
            self.combo_zoom_policy.setCurrentIndex(1)

    def apply_to_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            viewer._open_scan_dir_after_open = bool(self.chk_scan_after_open.isChecked())
        except Exception:
            pass
        try:
            viewer._remember_last_open_dir = bool(self.chk_remember_last_dir.isChecked())
        except Exception:
            pass
        try:
            viewer._anim_autoplay = bool(self.chk_anim_autoplay.isChecked())
            viewer._anim_loop = bool(self.chk_anim_loop.isChecked())
            viewer._anim_keep_state_on_switch = bool(self.chk_anim_keep_state.isChecked())
            viewer._anim_pause_on_unfocus = bool(self.chk_anim_pause_unfocus.isChecked())
            viewer._anim_click_toggle = bool(self.chk_anim_click_toggle.isChecked())
            viewer._anim_overlay_enabled = bool(self.chk_anim_overlay_enable.isChecked())
            viewer._anim_overlay_show_index = bool(self.chk_anim_overlay_show_index.isChecked())
            pos_idx = int(self.combo_anim_overlay_pos.currentIndex())
            viewer._anim_overlay_position = ("top-left" if pos_idx == 0 else ("top-right" if pos_idx == 1 else ("bottom-left" if pos_idx == 2 else "bottom-right")))
            viewer._anim_overlay_opacity = float(self.spin_anim_overlay_opacity.value())
        except Exception:
            pass
        try:
            pol_idx = int(self.combo_startup_restore.currentIndex())
            viewer._startup_restore_policy = ("always" if pol_idx == 0 else ("ask" if pol_idx == 1 else "never"))
        except Exception:
            pass
        try:
            viewer._recent_max_items = int(self.spin_recent_max.value())
            viewer._recent_auto_prune_missing = bool(self.chk_recent_auto_prune.isChecked())
        except Exception:
            pass
        try:
            is_explorer = (int(self.combo_sort_name.currentIndex()) == 0)
            viewer._dir_natural_sort = bool(is_explorer)
            viewer._dir_sort_mode = ("name" if is_explorer else ("metadata" if int(self.combo_sort_mode.currentIndex()) == 0 else "name"))
            self.combo_sort_mode.setEnabled(self.combo_sort_name.currentIndex() != 0)
        except Exception:
            pass
        try:
            viewer._dir_exclude_hidden_system = bool(self.chk_exclude_hidden.isChecked())
            viewer._tiff_open_first_page_only = bool(self.chk_tiff_first_page.isChecked())
        except Exception:
            pass
        try:
            viewer._nav_wrap_ends = bool(self.chk_wrap_ends.isChecked())
            viewer._nav_min_interval_ms = int(self.spin_nav_throttle.value())
            viewer._filmstrip_auto_center = bool(self.chk_film_center.isChecked())
            idx = int(self.combo_zoom_policy.currentIndex())
            viewer._zoom_policy = ("reset" if idx == 0 else ("mode" if idx == 1 else "scale"))
        except Exception:
            pass

    def reset_to_defaults(self) -> None:
        try:
            self.chk_scan_after_open.setChecked(True)
            self.chk_remember_last_dir.setChecked(True)
            self.chk_anim_autoplay.setChecked(True)
            self.chk_anim_loop.setChecked(True)
            self.chk_anim_keep_state.setChecked(False)
            self.chk_anim_pause_unfocus.setChecked(False)
            self.chk_anim_click_toggle.setChecked(False)
            self.chk_anim_overlay_enable.setChecked(False)
            self.chk_anim_overlay_show_index.setChecked(True)
            self.combo_anim_overlay_pos.setCurrentIndex(1)
            self.spin_anim_overlay_opacity.setValue(0.6)
            self.combo_startup_restore.setCurrentIndex(0)
            self.spin_recent_max.setValue(10)
            self.chk_recent_auto_prune.setChecked(True)
            self.combo_sort_mode.setCurrentIndex(0)
            self.combo_sort_name.setCurrentIndex(0)
            self.chk_exclude_hidden.setChecked(True)
            self.chk_wrap_ends.setChecked(False)
            self.spin_nav_throttle.setValue(100)
            self.chk_film_center.setChecked(True)
            self.combo_zoom_policy.setCurrentIndex(1)
            self.chk_tiff_first_page.setChecked(True)
        except Exception:
            pass


