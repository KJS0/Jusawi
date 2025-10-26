from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QDialogButtonBox, QCheckBox, QWidget, QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QApplication, QFormLayout, QFileDialog, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QKeySequenceEdit
from ..shortcuts.shortcuts_manager import COMMANDS, get_effective_keymap, save_custom_keymap
import os


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self._reset_keys_to_defaults = False
        self._key_warning_active = False

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
        except Exception:
            pass
        self.tabs = QTabWidget(self)
        root.addWidget(self.tabs)


        # ----- 일반 탭 -----
        self.general_tab = QWidget(self)
        self.tabs.addTab(self.general_tab, "일반")
        gen_layout = QVBoxLayout(self.general_tab)
        try:
            gen_layout.setContentsMargins(8, 8, 8, 8)
            gen_layout.setSpacing(8)
        except Exception:
            pass

        # 파일 열기 관련
        self.chk_scan_after_open = QCheckBox("열기 후 폴더 자동 스캔", self.general_tab)
        self.chk_remember_last_dir = QCheckBox("마지막 사용 폴더 기억", self.general_tab)
        gen_layout.addWidget(self.chk_scan_after_open)
        gen_layout.addWidget(self.chk_remember_last_dir)

        # 애니메이션
        gen_layout.addWidget(QLabel("애니메이션", self.general_tab))
        self.chk_anim_autoplay = QCheckBox("자동 재생", self.general_tab)
        self.chk_anim_loop = QCheckBox("루프 재생", self.general_tab)
        gen_layout.addWidget(self.chk_anim_autoplay)
        gen_layout.addWidget(self.chk_anim_loop)

        # 디렉터리 탐색 정렬/필터
        gen_layout.addWidget(QLabel("디렉터리 탐색", self.general_tab))
        self.combo_sort_mode = QComboBox(self.general_tab)
        self.combo_sort_mode.addItems(["메타데이터/촬영시간", "파일명"])
        self.combo_sort_name = QComboBox(self.general_tab)
        self.combo_sort_name.addItems(["자연 정렬", "사전식 정렬"])
        try:
            # 파일명 정렬 변경 시 즉시 정렬 기준 활성/비활성 토글
            self.combo_sort_name.currentIndexChanged.connect(lambda _idx: self._on_sort_name_changed())
        except Exception:
            pass
        self.chk_exclude_hidden = QCheckBox("숨김/시스템 파일 제외", self.general_tab)
        # 추가: 끝에서의 동작(순환), 연속 탐색 속도, 필름스트립 중앙정렬, 확대 유지 정책
        self.chk_wrap_ends = QCheckBox("끝에서 반대쪽으로 순환 이동", self.general_tab)
        self.spin_nav_throttle = QSpinBox(self.general_tab)
        self.spin_nav_throttle.setRange(0, 2000)
        self.spin_nav_throttle.setSuffix(" ms")
        self.chk_film_center = QCheckBox("필름스트립 항목을 자동 중앙 정렬", self.general_tab)
        self.combo_zoom_policy = QComboBox(self.general_tab)
        self.combo_zoom_policy.addItems(["전환 시 초기화", "보기 모드 유지", "배율 유지"])
        form = QFormLayout()
        form.addRow("정렬 기준", self.combo_sort_mode)
        form.addRow("파일명 정렬", self.combo_sort_name)
        form.addRow("필터", self.chk_exclude_hidden)
        form.addRow("끝에서의 동작", self.chk_wrap_ends)
        form.addRow("연속 탐색 속도", self.spin_nav_throttle)
        form.addRow("필름스트립 중앙 정렬", self.chk_film_center)
        form.addRow("확대 상태 유지", self.combo_zoom_policy)
        gen_layout.addLayout(form)

        # TIFF (라벨 옆에 체크박스 배치)
        from PyQt6.QtWidgets import QHBoxLayout  # type: ignore[import]
        tiff_row = QHBoxLayout()
        tiff_label = QLabel("TIFF", self.general_tab)
        self.chk_tiff_first_page = QCheckBox("항상 첫 페이지로 열기", self.general_tab)
        tiff_row.addWidget(tiff_label)
        tiff_row.addWidget(self.chk_tiff_first_page)
        tiff_row.addStretch(1)
        gen_layout.addLayout(tiff_row)

        # 단축키 탭 제거
        self._keys_ready = False

        # ----- 보기 탭 -----
        self.view_tab = QWidget(self)
        self.tabs.addTab(self.view_tab, "보기")
        view_layout = QVBoxLayout(self.view_tab)
        try:
            view_layout.setContentsMargins(8, 8, 8, 8)
            view_layout.setSpacing(8)
        except Exception:
            pass
        form_view = QFormLayout()
        # 기본 보기 모드
        self.combo_default_view = QComboBox(self.view_tab)
        self.combo_default_view.addItems(["화면 맞춤", "가로 맞춤", "세로 맞춤", "실제 크기"])  # fit/fit_width/fit_height/actual
        # 이미지 전환 시 처리 -> 기존 일반 탭의 combo_zoom_policy 사용(중복 방지)
        # 보기 공유 옵션 제거
        # 최소/최대 확대 비율(% 단위)
        from PyQt6.QtWidgets import QSpinBox as _IntSpin
        self.spin_min_scale = _IntSpin(self.view_tab); self.spin_min_scale.setRange(1, 1600); self.spin_min_scale.setSuffix(" %")
        self.spin_max_scale = _IntSpin(self.view_tab); self.spin_max_scale.setRange(1, 6400); self.spin_max_scale.setSuffix(" %")
        # 줌 단계
        self.chk_fixed_steps = QCheckBox("고정 줌 단계 사용", self.view_tab)
        self.spin_zoom_step = QDoubleSpinBox(self.view_tab); self.spin_zoom_step.setRange(1.02, 2.5); self.spin_zoom_step.setSingleStep(0.01)
        self.spin_precise_step = QDoubleSpinBox(self.view_tab); self.spin_precise_step.setRange(1.01, 2.0); self.spin_precise_step.setSingleStep(0.01)
        # 리샘플링 품질/보간
        self.chk_smooth = QCheckBox("고품질 보간(스무딩)", self.view_tab)
        # 화면 맞춤 여백
        self.spin_fit_margin = QSpinBox(self.view_tab); self.spin_fit_margin.setRange(0, 40); self.spin_fit_margin.setSuffix(" %")
        # 휠/트랙패드 제스처
        self.chk_wheel_requires_ctrl = QCheckBox("휠 줌에 Ctrl 필요", self.view_tab)
        self.chk_alt_precise = QCheckBox("Alt+휠 정밀 줌 허용", self.view_tab)
        # 더블클릭/휠클릭 동작
        self.combo_dbl = QComboBox(self.view_tab); self.combo_dbl.addItems(["토글(화면↔100%)", "화면 맞춤", "가로 맞춤", "세로 맞춤", "실제 크기", "없음"])  # toggle/fit/fit_width/fit_height/actual/none
        self.combo_mid = QComboBox(self.view_tab); self.combo_mid.addItems(["없음", "토글(화면↔100%)", "화면 맞춤", "실제 크기"])  # none/toggle/fit/actual
        # 회전/반전 시 재맞춤 여부
        self.chk_refit_on_tf = QCheckBox("회전/반전 후 자동 재맞춤", self.view_tab)
        # DPR 옵션
        self.chk_preserve_visual_dpr = QCheckBox("DPR 변경 시 시각 크기 유지", self.view_tab)
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
        form_view.addRow("DPR 시각 크기 유지", self.chk_preserve_visual_dpr)
        view_layout.addLayout(form_view)
        # ----- 전체화면/오버레이 탭 -----
        self.fullscreen_tab = QWidget(self)
        self.tabs.addTab(self.fullscreen_tab, "전체화면")
        fs_layout = QVBoxLayout(self.fullscreen_tab)
        try:
            fs_layout.setContentsMargins(8, 8, 8, 8)
            fs_layout.setSpacing(8)
        except Exception:
            pass
        self.spin_fs_auto_hide = QSpinBox(self.fullscreen_tab)
        self.spin_fs_auto_hide.setRange(0, 10000)
        self.spin_fs_auto_hide.setSuffix(" ms")
        self.spin_cursor_hide = QSpinBox(self.fullscreen_tab)
        self.spin_cursor_hide.setRange(0, 10000)
        self.spin_cursor_hide.setSuffix(" ms")
        self.combo_fs_viewmode = QComboBox(self.fullscreen_tab)
        self.combo_fs_viewmode.addItems(["유지", "화면 맞춤", "가로 맞춤", "세로 맞춤", "실제 크기"])
        self.chk_fs_show_filmstrip = QCheckBox("전체화면에서 필름스트립 오버레이 표시", self.fullscreen_tab)
        self.chk_fs_safe_exit = QCheckBox("Esc 안전 종료(1단계: UI 표시, 2단계: 종료)", self.fullscreen_tab)
        self.chk_overlay_default = QCheckBox("앱 시작 시 정보 오버레이 표시", self.fullscreen_tab)
        fs_form = QFormLayout()
        fs_form.addRow("UI 자동 숨김 지연", self.spin_fs_auto_hide)
        fs_form.addRow("커서 자동 숨김 지연", self.spin_cursor_hide)
        fs_form.addRow("진입 시 보기 모드", self.combo_fs_viewmode)
        fs_form.addRow("필름스트립 오버레이", self.chk_fs_show_filmstrip)
        fs_form.addRow("안전 종료 규칙", self.chk_fs_safe_exit)
        fs_form.addRow("정보 오버레이 기본 표시", self.chk_overlay_default)
        fs_layout.addLayout(fs_form)

        # 하단: 우측 확인/취소만 표시
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        # 기본 설정으로 재설정 버튼(좌측)
        self.btn_reset_all = QPushButton("기본 설정으로 재설정", self)
        try:
            self.btn_reset_all.clicked.connect(self._on_reset_all_defaults)
        except Exception:
            pass
        bottom_row.addWidget(self.btn_reset_all)
        bottom_row.addStretch(1)
        root.addLayout(bottom_row)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        # 탭 변경 시 크기 최적화
        try:
            self.tabs.currentChanged.connect(self._on_tab_changed)
        except Exception:
            pass
        # 초기 크기: 일반 탭에 맞춰 컴팩트하게
        try:
            self._on_tab_changed(0)
        except Exception:
            pass

    # 외부에서 호출: 단축키 탭으로 전환하고 첫 편집기로 포커스 이동
    def focus_shortcuts_tab(self):
        try:
            # 탭 전환
            idx = self.tabs.indexOf(self.keys_tab)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)
            # 필요 시 지연 초기화 실행
            if not getattr(self, "_keys_ready", False):
                self._build_keys_tab()
            # 첫 편집 가능한 필드로 포커스
            for ed in getattr(self, "_key_editors", []) or []:
                meta = getattr(self, "_editor_meta", {}).get(ed, {})
                if not meta.get("locked", False):
                    try:
                        ed.setFocus()
                        break
                    except Exception:
                        pass
        except Exception:
            pass

    # populate from viewer
    def load_from_viewer(self, viewer):
        # viewer 참조 저장(지연 로드시 사용)
        self._viewer_for_keys = viewer
        # 일반 탭 값 반영
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
            mode = str(getattr(viewer, "_dir_sort_mode", "metadata"))
            self.combo_sort_mode.setCurrentIndex(0 if mode == "metadata" else 1)
        except Exception:
            self.combo_sort_mode.setCurrentIndex(0)
        try:
            self.combo_sort_name.setCurrentIndex(0 if bool(getattr(viewer, "_dir_natural_sort", True)) else 1)
        except Exception:
            self.combo_sort_name.setCurrentIndex(0)
        # 자연 정렬이면 정렬 기준 비활성화
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
        # 추가 옵션 로드
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
        # 전체화면/오버레이 로드
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
        # 보기 탭 로드
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
            self.chk_preserve_visual_dpr.setChecked(bool(getattr(viewer, "_preserve_visual_size_on_dpr_change", False)))
        except Exception:
            self.chk_preserve_visual_dpr.setChecked(False)

    # commit back to viewer (does not save)
    def apply_to_viewer(self, viewer):
        # 키 저장(중복/금지 키 검증 포함)
        mapping = None
        if self._reset_keys_to_defaults:
            # 키 탭이 열려있지 않아도 기본값으로 저장
            mapping = {}
            for cmd in COMMANDS:
                if cmd.lock_key:
                    continue
                mapping[cmd.id] = cmd.default_keys[:1]
        elif getattr(self, "_keys_ready", False):
            mapping = self._collect_mapping_from_ui(validate_against_fixed=True)
            if mapping is None:
                return
        if mapping is not None:
            save_custom_keymap(getattr(viewer, "settings", None), mapping)
        self._reset_keys_to_defaults = False
        # 일반 탭 → viewer에 즉시 반영
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
        except Exception:
            pass
        try:
            viewer._anim_loop = bool(self.chk_anim_loop.isChecked())
        except Exception:
            pass
        try:
            viewer._dir_sort_mode = "metadata" if int(self.combo_sort_mode.currentIndex()) == 0 else "name"
        except Exception:
            pass
        try:
            viewer._dir_natural_sort = bool(int(self.combo_sort_name.currentIndex()) == 0)
        except Exception:
            pass
        # 자연 정렬이면 기준 강제 파일명, UI 비활성화 정책 유지
        try:
            self.combo_sort_mode.setEnabled(self.combo_sort_name.currentIndex() != 0)
        except Exception:
            pass
        try:
            viewer._dir_exclude_hidden_system = bool(self.chk_exclude_hidden.isChecked())
        except Exception:
            pass
        try:
            viewer._tiff_open_first_page_only = bool(self.chk_tiff_first_page.isChecked())
        except Exception:
            pass
        # 추가 옵션 적용
        try:
            viewer._nav_wrap_ends = bool(self.chk_wrap_ends.isChecked())
        except Exception:
            pass
        try:
            viewer._nav_min_interval_ms = int(self.spin_nav_throttle.value())
        except Exception:
            pass
        try:
            viewer._filmstrip_auto_center = bool(self.chk_film_center.isChecked())
        except Exception:
            pass
        try:
            idx = int(self.combo_zoom_policy.currentIndex())
            viewer._zoom_policy = ("reset" if idx == 0 else ("mode" if idx == 1 else "scale"))
        except Exception:
            pass
        # 전체화면/오버레이 적용
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
        # 보기 탭 적용
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
            # 렌더 힌트 즉시 반영
            if hasattr(viewer, 'image_display_area') and viewer.image_display_area is not None:
                iv = viewer.image_display_area
                from PyQt6.QtGui import QPainter
                hints = iv.renderHints()
                if viewer._smooth_transform:
                    hints |= QPainter.RenderHint.SmoothPixmapTransform
                else:
                    hints &= ~QPainter.RenderHint.SmoothPixmapTransform
                iv.setRenderHints(hints)
        except Exception:
            pass
        try:
            viewer._fit_margin_pct = int(self.spin_fit_margin.value())
        except Exception:
            pass
        try:
            viewer._wheel_zoom_requires_ctrl = bool(self.chk_wheel_requires_ctrl.isChecked())
            viewer._wheel_zoom_alt_precise = bool(self.chk_alt_precise.isChecked())
        except Exception:
            pass
        try:
            di = int(self.combo_dbl.currentIndex())
            viewer._double_click_action = ("toggle" if di == 0 else ("fit" if di == 1 else ("fit_width" if di == 2 else ("fit_height" if di == 3 else ("actual" if di == 4 else "none")))))
        except Exception:
            pass
        try:
            mi = int(self.combo_mid.currentIndex())
            viewer._middle_click_action = ("none" if mi == 0 else ("toggle" if mi == 1 else ("fit" if mi == 2 else "actual")))
        except Exception:
            pass
        try:
            viewer._refit_on_transform = bool(self.chk_refit_on_tf.isChecked())
        except Exception:
            pass
        try:
            viewer._preserve_visual_size_on_dpr_change = bool(self.chk_preserve_visual_dpr.isChecked())
        except Exception:
            pass
        # 파일 관련 설정 변경 시, 캐시/썸네일까지 리셋 후 현재 폴더를 새로운 기준으로 재스캔(현재 파일은 유지)
        try:
            cur = getattr(viewer, "current_image_path", "") or ""
            if cur and os.path.isfile(cur):
                try:
                    viewer.image_service.clear_all_caches()
                except Exception:
                    pass
                try:
                    # 썸네일 메모리 캐시도 초기화
                    if hasattr(viewer, "_clear_filmstrip_cache") and callable(viewer._clear_filmstrip_cache):
                        viewer._clear_filmstrip_cache()
                except Exception:
                    pass
                d = os.path.dirname(cur)
                if d and os.path.isdir(d):
                    viewer.scan_directory(d)
                    # 재정렬된 목록에서 현재 파일 인덱스 복원 또는 대체 파일 적용
                    try:
                        nc = os.path.normcase
                        if viewer.image_files_in_dir:
                            try:
                                idx = [nc(p) for p in viewer.image_files_in_dir].index(nc(cur))
                                viewer.current_image_index = idx
                                viewer.load_image_at_current_index()
                            except ValueError:
                                # 현재 파일이 목록에서 제외되었다면 첫 항목으로 대체 로드
                                viewer.current_image_index = 0
                                viewer.load_image_at_current_index()
                    except Exception:
                        pass
        except Exception:
            pass

    def _on_sort_name_changed(self):
        try:
            self.combo_sort_mode.setEnabled(self.combo_sort_name.currentIndex() != 0)
        except Exception:
            pass

    # ----- helpers -----
    def _on_reset_defaults(self):
        # 단축키 탭 기본값: 레지스트리의 default_keys로 되돌림(없으면 비움)
        # 테이블은 COMMANDS 순으로 채워져 있음
        if getattr(self, "_keys_ready", False) and hasattr(self, "keys_table"):
            row = 0
            for cmd in COMMANDS:
                editor = self.keys_table.cellWidget(row, 3) if row < self.keys_table.rowCount() else None
                if isinstance(editor, QKeySequenceEdit):
                    defaults = cmd.default_keys[:]
                    editor.setKeySequence(QKeySequence(defaults[0]) if defaults else QKeySequence())
                row += 1
        self._reset_keys_to_defaults = True

    def _on_reset_all_defaults(self):
        # 일반 탭 기본값으로 초기화하고 즉시 적용/저장
        try:
            self.chk_scan_after_open.setChecked(True)
            self.chk_remember_last_dir.setChecked(True)
            self.chk_anim_autoplay.setChecked(True)
            self.chk_anim_loop.setChecked(True)
            self.combo_sort_mode.setCurrentIndex(0)
            self.combo_sort_name.setCurrentIndex(0)
            self.chk_exclude_hidden.setChecked(True)
            self.chk_tiff_first_page.setChecked(True)
            self.chk_wrap_ends.setChecked(False)
            self.spin_nav_throttle.setValue(100)
            self.chk_film_center.setChecked(True)
            self.combo_zoom_policy.setCurrentIndex(1)
            # 뷰어에 즉시 반영 및 저장
            viewer = getattr(self, "_viewer_for_keys", None)
            if viewer is not None:
                self.apply_to_viewer(viewer)
                try:
                    viewer.save_settings()
                except Exception:
                    pass
        except Exception:
            pass

    def _on_accept(self):
        # 적용 전에 유효성 검사 수행 후 통과하면 accept
        # viewer에 직접 접근하지 않고 저장할 매핑만 검증
        if not self._reset_keys_to_defaults and not getattr(self, "_keys_ready", False):
            # 키 탭이 초기화되지 않았다면 단축키 검증은 건너뜀
            self.accept()
            return
        mapping = self._collect_mapping_from_ui(validate_against_fixed=True)
        if mapping is None:
            return
        self.accept()

    def _on_import_yaml(self):
        # 제거됨
        return

    def _on_export_yaml(self):
        # 제거됨
        return

    def _on_tab_changed(self, index: int):
        # 일반 탭은 작게, 단축키 탭은 내용 기반으로 크게
        try:
            tab_text = self.tabs.tabText(index)
        except Exception:
            tab_text = ""
        if tab_text == "단축키":
            # 지연 초기화
            if not getattr(self, "_keys_ready", False):
                try:
                    self._build_keys_tab()
                except Exception:
                    pass
            try:
                # 단축키 탭 크기 재조정
                header = self.keys_table.horizontalHeader()
                header.resizeSections(QHeaderView.ResizeMode.ResizeToContents)
            except Exception:
                pass
            # 기본 넉넉한 크기
            self.resize(max(860, self.width()), max(520, self.height()))
        else:
            # 일반 탭: 컴팩트 크기 강제
            self.resize(520, 360)

        # 자연 정렬 UI 규칙 동기화
        try:
            self.combo_sort_mode.setEnabled(self.combo_sort_name.currentIndex() != 0)
        except Exception:
            pass

    def _build_keys_tab(self):
        # 실제 키 탭 UI 구성 및 데이터 로드
        keys_layout = QVBoxLayout(self.keys_tab)
        self.keys_table = QTableWidget(0, 4, self.keys_tab)
        self.keys_table.setHorizontalHeaderLabels(["조건", "명령", "설명", "단축키"])
        try:
            # 표 셀 선택/편집 비활성화(편집기는 별도 위젯으로 사용)
            from PyQt6.QtWidgets import QAbstractItemView
            self.keys_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.keys_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        except Exception:
            pass
        keys_layout.addWidget(self.keys_table)
        self._keys_ready = True
        # 데이터 채우기
        viewer = getattr(self, "_viewer_for_keys", None)
        eff = get_effective_keymap(getattr(viewer, "settings", None))
        self.keys_table.setRowCount(0)
        self._key_editors = []
        self._editor_meta = {}
        for cmd in [c for c in COMMANDS if c.id != "reset_to_100"]:
            row = self.keys_table.rowCount()
            self.keys_table.insertRow(row)
            cond_text = "고정" if cmd.lock_key else "-"
            it0 = QTableWidgetItem(cond_text)
            it1 = QTableWidgetItem(cmd.label)
            it2 = QTableWidgetItem(cmd.desc)
            # 입력/선택 불가, 표시만
            try:
                it0.setFlags(Qt.ItemFlag.ItemIsEnabled)
                it1.setFlags(Qt.ItemFlag.ItemIsEnabled)
                it2.setFlags(Qt.ItemFlag.ItemIsEnabled)
            except Exception:
                pass
            self.keys_table.setItem(row, 0, it0)
            self.keys_table.setItem(row, 1, it1)
            self.keys_table.setItem(row, 2, it2)
            # 읽기 전용 텍스트로 표시(여러 키가 있을 경우 ; 로 연결)
            seqs = eff.get(cmd.id, []) or []
            txt = "; ".join([str(s) for s in seqs]) if seqs else ""
            it3 = QTableWidgetItem(txt)
            try:
                it3.setFlags(Qt.ItemFlag.ItemIsEnabled)
            except Exception:
                pass
            self.keys_table.setItem(row, 3, it3)
        # 컬럼/크기 조정
        try:
            header = self.keys_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            self.keys_table.resizeColumnsToContents()
        except Exception:
            pass

    def _collect_mapping_from_ui(self, validate_against_fixed: bool = True):
        from PyQt6.QtWidgets import QMessageBox
        # 열람 전용: 현재 테이블의 텍스트를 그대로 저장 대상으로 수집
        mapping: dict[str, list[str]] = {}
        if getattr(self, "_keys_ready", False) and hasattr(self, "keys_table"):
            for row in range(self.keys_table.rowCount()):
                cmd = COMMANDS[row]
                item = self.keys_table.item(row, 3)
                txt = item.text().strip() if item else ""
                mapping[cmd.id] = [txt] if txt else []

        # 유효성 검사: 중복, 고정키 충돌, 예약키 금지
        if validate_against_fixed:
            used: dict[str, str] = {}
            # 고정키(F1, Escape 등) 집합
            fixed_keys = set()
            for cmd in COMMANDS:
                if cmd.lock_key:
                    for k in cmd.default_keys:
                        if k:
                            fixed_keys.add(k)
            # 예약키(확장 가능)
            # Space는 애니메이션 전용 고정키이므로 일반 명령으로 저장 시 충돌 처리
            reserved = {"Alt+F4"}

            # 중복 및 금지 검사
            for cmd in COMMANDS:
                if cmd.lock_key:
                    continue
                keys = mapping.get(cmd.id, []) or []
                if not keys:
                    continue
                k = keys[0]
                if k in reserved:
                    QMessageBox.warning(self, "단축키 오류", f"예약된 단축키 '{k}' 는 사용할 수 없습니다.")
                    return None
                if k in fixed_keys:
                    # Space는 조용히 무시
                    if k == "Space":
                        mapping[cmd.id] = []
                        continue
                    QMessageBox.warning(self, "단축키 충돌", f"'{k}' 는 시스템/고정 단축키와 충돌합니다.")
                    return None
                if k in used:
                    # 다른 명령과 중복
                    other = used[k]
                    QMessageBox.warning(self, "단축키 중복", f"'{k}' 가 '{other}' 와(과) 중복됩니다. 다른 키를 지정하세요.")
                    return None
                used[k] = cmd.label

        return mapping

    def _normalize_single_key(self, editor: QKeySequenceEdit):
        try:
            seq = editor.keySequence()
            if not seq or seq.isEmpty():
                return
            # 표준 텍스트로 변환
            try:
                from PyQt6.QtGui import QKeySequence as _QS
                text = seq.toString(_QS.SequenceFormat.PortableText)
            except Exception:
                text = seq.toString()
            # 여러 파트가 "," 로 구분되어 들어올 수 있으므로 마지막 파트만 유지
            parts = [p.strip() for p in text.split(',') if p.strip()]
            last_part = parts[-1] if parts else ''
            # 수정키만 있는 조합 문자열 집합(PortableText 기준)
            mod_only = {
                "Ctrl", "Shift", "Alt", "Meta",
                "Ctrl+Shift", "Ctrl+Alt", "Ctrl+Meta",
                "Shift+Alt", "Shift+Meta", "Alt+Meta",
                "Ctrl+Shift+Alt", "Ctrl+Shift+Meta", "Ctrl+Alt+Meta",
                "Shift+Alt+Meta", "Ctrl+Shift+Alt+Meta"
            }
            if last_part in mod_only:
                editor.blockSignals(True)
                editor.setKeySequence(QKeySequence())
                editor.blockSignals(False)
                return
            # 최종 1개 시퀀스로 고정
            editor.blockSignals(True)
            editor.setKeySequence(QKeySequence(last_part))
            editor.blockSignals(False)
        except Exception:
            pass

    def _on_key_changed(self, editor: QKeySequenceEdit, defaults: list, row_idx: int):
        # 정규화 수행
        self._normalize_single_key(editor)
        # 중복/금지/고정 충돌 즉시 검사
        try:
            cur_txt = self._seq_to_text(editor.keySequence())
            def_txt = self._normalize_default_text(defaults)
            # 빈 값이면 버튼만 동기화하고 끝
            if not cur_txt:
                btn = self.keys_table.cellWidget(row_idx, 4)
                if isinstance(btn, QPushButton):
                    btn.setEnabled(False)
                return
            # 고정키/예약키 집합
            fixed_keys = set()
            for cmd in COMMANDS:
                if cmd.lock_key:
                    for k in cmd.default_keys:
                        if k:
                            fixed_keys.add(k)
            reserved = {"Alt+F4"}
            # 현재 행 외 사용중 키 수집
            used = set()
            for r in range(self.keys_table.rowCount()):
                if r == row_idx:
                    continue
                item = self.keys_table.item(r, 3)
                k = item.text().strip() if item else ""
                if k:
                    used.add(k)
            if cur_txt in reserved:
                self._show_key_warning("단축키 오류", f"예약된 단축키 '{cur_txt}' 는 사용할 수 없습니다.", editor)
                meta = getattr(self, "_editor_meta", {}).get(editor, {})
                prev_txt = meta.get("prev", "") if isinstance(meta, dict) else ""
                editor.blockSignals(True)
                editor.setKeySequence(QKeySequence(prev_txt) if prev_txt else QKeySequence())
                editor.blockSignals(False)
                cur_txt = prev_txt
            elif cur_txt in fixed_keys:
                # Space는 조용히 무시, 그 외에는 경고
                if cur_txt == "Space":
                    meta = getattr(self, "_editor_meta", {}).get(editor, {})
                    prev_txt = meta.get("prev", "") if isinstance(meta, dict) else ""
                    editor.blockSignals(True)
                    editor.setKeySequence(QKeySequence(prev_txt) if prev_txt else QKeySequence())
                    editor.blockSignals(False)
                    cur_txt = prev_txt
                else:
                    self._show_key_warning("단축키 충돌", f"'{cur_txt}' 는 시스템/고정 단축키와 충돌합니다.", editor)
                    meta = getattr(self, "_editor_meta", {}).get(editor, {})
                    prev_txt = meta.get("prev", "") if isinstance(meta, dict) else ""
                    editor.blockSignals(True)
                    editor.setKeySequence(QKeySequence(prev_txt) if prev_txt else QKeySequence())
                    editor.blockSignals(False)
                    cur_txt = prev_txt
            elif cur_txt in used:
                self._show_key_warning("단축키 중복", f"'{cur_txt}' 가 이미 다른 명령에 할당되어 있습니다.", editor)
                meta = getattr(self, "_editor_meta", {}).get(editor, {})
                prev_txt = meta.get("prev", "") if isinstance(meta, dict) else ""
                editor.blockSignals(True)
                editor.setKeySequence(QKeySequence(prev_txt) if prev_txt else QKeySequence())
                editor.blockSignals(False)
                cur_txt = prev_txt
            # 기본값 버튼 상태 업데이트
            btn = self.keys_table.cellWidget(row_idx, 4)
            if isinstance(btn, QPushButton):
                btn.setEnabled(bool(def_txt) and cur_txt != def_txt)
        except Exception:
            pass

    def _show_key_warning(self, title: str, text: str, editor: QKeySequenceEdit | None):
        # 동일 시점 중복 팝업 방지 및 포커스 이동 보장
        try:
            if self._key_warning_active:
                return
            self._key_warning_active = True
            from PyQt6.QtWidgets import QMessageBox
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(title)
            box.setText(text)
            box.setWindowModality(Qt.WindowModality.ApplicationModal)
            try:
                box.raise_()
                box.activateWindow()
            except Exception:
                pass
            box.exec()
        except Exception:
            pass
        finally:
            self._key_warning_active = False
            try:
                if editor is not None:
                    editor.setFocus()
            except Exception:
                pass

    def _seq_to_text(self, seq: QKeySequence) -> str:
        try:
            from PyQt6.QtGui import QKeySequence as _QS
            return seq.toString(_QS.SequenceFormat.PortableText) if seq and not seq.isEmpty() else ""
        except Exception:
            return seq.toString() if seq and not seq.isEmpty() else ""

    def _normalize_default_text(self, defaults: list) -> str:
        if not defaults:
            return ""
        return str(defaults[0])

    # 이벤트 필터: 배타 포커스 + Backspace/Delete로 해제 지원
    def eventFilter(self, obj, event):
        try:
            if isinstance(obj, QKeySequenceEdit):
                if event.type() == QEvent.Type.FocusIn:
                    # 다른 에디터 포커스 제거
                    for ed in getattr(self, "_key_editors", []) or []:
                        if ed is not obj and ed.hasFocus():
                            try:
                                ed.clearFocus()
                            except Exception:
                                pass
                elif event.type() == QEvent.Type.KeyPress:
                    key = getattr(event, 'key', None)
                    # Backspace/Delete 처리: 키 해제
                    if key and int(key()) in (0x01000003, 0x01000007):  # Qt.Key_Backspace, Qt.Key_Delete
                        obj.setKeySequence(QKeySequence())
                        meta = getattr(self, "_editor_meta", {}).get(obj, None)
                        if meta is not None:
                            self._on_key_changed(obj, meta.get("defaults", []), int(meta.get("row", 0)))
                        return True
        except Exception:
            pass
        return super().eventFilter(obj, event)


class _LabeledRow(QHBoxLayout):
    def __init__(self, label_text: str):
        super().__init__()
        try:
            self.setContentsMargins(0, 0, 0, 0)
            self.setSpacing(0)
        except Exception:
            pass
        self._label = QLabel(label_text)
        try:
            self._label.setMinimumWidth(0)
            self._label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        except Exception:
            pass
        self.addWidget(self._label)
        self._holder = QWidget()
        self._holder_layout = QHBoxLayout(self._holder)
        try:
            self._holder_layout.setContentsMargins(0, 0, 0, 0)
            self._holder_layout.setSpacing(0)
        except Exception:
            pass
        self.addWidget(self._holder, 1)

    def set_widget(self, w: QWidget):
        # clear holder
        while self._holder_layout.count():
            item = self._holder_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._holder_layout.addWidget(w)


def _spin(min_v: int, max_v: int, value: int) -> QSpinBox:
    s = QSpinBox()
    s.setRange(min_v, max_v)
    s.setValue(value)
    return s


