from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QDialogButtonBox, QCheckBox, QWidget, QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QApplication, QFormLayout, QFileDialog, QDoubleSpinBox, QScrollArea
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
        # 일반 탭을 스크롤 가능하게 구성
        gen_root = QVBoxLayout(self.general_tab)
        try:
            gen_root.setContentsMargins(0, 0, 0, 0)
            gen_root.setSpacing(0)
        except Exception:
            pass
        _gen_scroll = QScrollArea(self.general_tab)
        try:
            _gen_scroll.setWidgetResizable(True)
        except Exception:
            pass
        _gen_page = QWidget()
        _gen_scroll.setWidget(_gen_page)
        gen_layout = QVBoxLayout(_gen_page)
        try:
            gen_layout.setContentsMargins(8, 8, 8, 8)
            gen_layout.setSpacing(8)
        except Exception:
            pass
        gen_root.addWidget(_gen_scroll)

        # 파일 열기 관련
        self.chk_scan_after_open = QCheckBox("열기 후 폴더 자동 스캔", self.general_tab)
        self.chk_remember_last_dir = QCheckBox("마지막 사용 폴더 기억", self.general_tab)
        gen_layout.addWidget(self.chk_scan_after_open)
        gen_layout.addWidget(self.chk_remember_last_dir)

        # 세션/최근 목록 옵션
        gen_layout.addWidget(QLabel("세션/최근", self.general_tab))
        self.combo_startup_restore = QComboBox(self.general_tab)
        self.combo_startup_restore.addItems(["항상 복원", "묻기", "복원 안 함"])  # always/ask/never
        self.spin_recent_max = QSpinBox(self.general_tab); self.spin_recent_max.setRange(1, 100); self.spin_recent_max.setSuffix(" 개")
        self.chk_recent_auto_prune = QCheckBox("존재하지 않는 항목 자동 정리", self.general_tab)
        form_recent = QFormLayout()
        form_recent.addRow("시작 시 세션 복원", self.combo_startup_restore)
        form_recent.addRow("최근 목록 최대 개수", self.spin_recent_max)
        # 제외 규칙 UI 삭제
        form_recent.addRow("존재하지 않음 자동 정리", self.chk_recent_auto_prune)
        gen_layout.addLayout(form_recent)

        # 애니메이션
        gen_layout.addWidget(QLabel("애니메이션", self.general_tab))
        self.chk_anim_autoplay = QCheckBox("자동 재생", self.general_tab)
        self.chk_anim_loop = QCheckBox("루프 재생", self.general_tab)
        # 신규 옵션: 파일 전환 시 재생 상태 유지, 비활성화 시 일시정지, 클릭 토글, 프레임 오버레이
        self.chk_anim_keep_state = QCheckBox("파일 전환 시 재생 상태 유지", self.general_tab)
        self.chk_anim_pause_unfocus = QCheckBox("비활성화 시 자동 일시정지", self.general_tab)
        self.chk_anim_click_toggle = QCheckBox("이미지 클릭으로 재생/일시정지", self.general_tab)
        self.chk_anim_overlay_enable = QCheckBox("프레임 오버레이 표시", self.general_tab)
        self.chk_anim_overlay_show_index = QCheckBox("프레임 번호/총 프레임 표시", self.general_tab)
        self.combo_anim_overlay_pos = QComboBox(self.general_tab)
        self.combo_anim_overlay_pos.addItems(["좌상", "우상", "좌하", "우하"])  # top-left/top-right/bottom-left/bottom-right
        self.spin_anim_overlay_opacity = QDoubleSpinBox(self.general_tab); self.spin_anim_overlay_opacity.setRange(0.05, 1.0); self.spin_anim_overlay_opacity.setSingleStep(0.05)
        # 배치
        gen_layout.addWidget(self.chk_anim_autoplay)
        gen_layout.addWidget(self.chk_anim_loop)
        form_anim = QFormLayout()
        form_anim.addRow("재생 상태 유지", self.chk_anim_keep_state)
        form_anim.addRow("비활성화 시 일시정지", self.chk_anim_pause_unfocus)
        form_anim.addRow("클릭으로 재생/일시정지", self.chk_anim_click_toggle)
        form_anim.addRow("오버레이 표시", self.chk_anim_overlay_enable)
        form_anim.addRow("프레임 텍스트", self.chk_anim_overlay_show_index)
        form_anim.addRow("오버레이 위치", self.combo_anim_overlay_pos)
        form_anim.addRow("오버레이 불투명도", self.spin_anim_overlay_opacity)
        gen_layout.addLayout(form_anim)

        # 디렉터리 탐색 정렬/필터
        gen_layout.addWidget(QLabel("디렉터리 탐색", self.general_tab))
        self.combo_sort_mode = QComboBox(self.general_tab)
        self.combo_sort_mode.addItems(["메타데이터/촬영시간", "파일명"])
        self.combo_sort_name = QComboBox(self.general_tab)
        self.combo_sort_name.addItems(["윈도우 탐색기 정렬", "사전식 정렬"])
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

        # 드래그 앤 드롭 옵션
        gen_layout.addWidget(QLabel("드래그 앤 드롭", self.general_tab))
        self.chk_drop_allow_folder = QCheckBox("폴더 드롭 허용", self.general_tab)
        self.chk_drop_parent_scan = QCheckBox("부모 폴더 스캔으로 전체 탐색", self.general_tab)
        self.chk_drop_overlay = QCheckBox("대용량 드롭 진행 오버레이 표시", self.general_tab)
        self.chk_drop_confirm = QCheckBox("파일 수 임계치 초과 시 확인창", self.general_tab)
        self.spin_drop_threshold = QSpinBox(self.general_tab); self.spin_drop_threshold.setRange(50, 100000); self.spin_drop_threshold.setSuffix(" 개")
        form_dnd = QFormLayout()
        form_dnd.addRow("폴더 드롭", self.chk_drop_allow_folder)
        form_dnd.addRow("목록 구성", self.chk_drop_parent_scan)
        form_dnd.addRow("진행 오버레이", self.chk_drop_overlay)
        form_dnd.addRow("대용량 확인", self.chk_drop_confirm)
        form_dnd.addRow("임계치", self.spin_drop_threshold)
        gen_layout.addLayout(form_dnd)

        # 자동화
        gen_layout.addWidget(QLabel("자동화", self.general_tab))
        self.chk_ai_auto = QCheckBox("사진 열기/드롭 후 AI 분석 자동 실행", self.general_tab)
        self.spin_ai_delay = QSpinBox(self.general_tab); self.spin_ai_delay.setRange(0, 60000); self.spin_ai_delay.setSuffix(" ms")
        form_auto = QFormLayout()
        form_auto.addRow("AI 자동 실행", self.chk_ai_auto)
        form_auto.addRow("지연 시간", self.spin_ai_delay)
        gen_layout.addLayout(form_auto)

        # TIFF (라벨 옆에 체크박스 배치)
        from PyQt6.QtWidgets import QHBoxLayout  # type: ignore[import]
        tiff_row = QHBoxLayout()
        tiff_label = QLabel("TIFF", self.general_tab)
        self.chk_tiff_first_page = QCheckBox("항상 첫 페이지로 열기", self.general_tab)
        tiff_row.addWidget(tiff_label)
        tiff_row.addWidget(self.chk_tiff_first_page)
        tiff_row.addStretch(1)
        gen_layout.addLayout(tiff_row)

        # ----- 성능/프리패치 탭 -----
        self.perf_tab = QWidget(self)
        self.tabs.addTab(self.perf_tab, "성능/프리패치")
        perf_layout = QVBoxLayout(self.perf_tab)
        try:
            perf_layout.setContentsMargins(8, 8, 8, 8)
            perf_layout.setSpacing(8)
        except Exception:
            pass

        perf_layout.addWidget(QLabel("성능/프리페치", self.perf_tab))
        self.chk_prefetch_thumbs = QCheckBox("썸네일/이웃 이미지 프리로드", self.perf_tab)
        self.spin_preload_radius = QSpinBox(self.perf_tab); self.spin_preload_radius.setRange(0, 20); self.spin_preload_radius.setSuffix(" 장")
        self.chk_prefetch_map = QCheckBox("지도 캐시 프리페치", self.perf_tab)
        # 프리로드 방향/우선순위/동시 작업 수
        self.combo_preload_direction = QComboBox(self.perf_tab)
        self.combo_preload_direction.addItems(["양방향", "앞쪽", "뒤쪽"])  # both/forward/backward
        self.spin_preload_priority = QSpinBox(self.perf_tab); self.spin_preload_priority.setRange(-10, 10); self.spin_preload_priority.setSuffix(" prio")
        self.spin_preload_concurrency = QSpinBox(self.perf_tab); self.spin_preload_concurrency.setRange(0, 16); self.spin_preload_concurrency.setSuffix(" 개")
        self.spin_preload_retry = QSpinBox(self.perf_tab); self.spin_preload_retry.setRange(0, 5); self.spin_preload_retry.setSuffix(" 회")
        self.spin_preload_retry_delay = QSpinBox(self.perf_tab); self.spin_preload_retry_delay.setRange(0, 5000); self.spin_preload_retry_delay.setSuffix(" ms")
        # 캐시 상한
        self.spin_img_cache_mb = QSpinBox(self.perf_tab); self.spin_img_cache_mb.setRange(32, 4096); self.spin_img_cache_mb.setSuffix(" MB")
        self.spin_scaled_cache_mb = QSpinBox(self.perf_tab); self.spin_scaled_cache_mb.setRange(32, 8192); self.spin_scaled_cache_mb.setSuffix(" MB")
        self.spin_cache_auto_shrink_pct = QSpinBox(self.perf_tab); self.spin_cache_auto_shrink_pct.setRange(10, 90); self.spin_cache_auto_shrink_pct.setSuffix(" %")
        self.spin_cache_gc_interval = QSpinBox(self.perf_tab); self.spin_cache_gc_interval.setRange(0, 600); self.spin_cache_gc_interval.setSuffix(" s")
        form_pf = QFormLayout()
        # 대용량 이미지 프리뷰/업그레이드 정책
        self.spin_upgrade_delay = QSpinBox(self.perf_tab); self.spin_upgrade_delay.setRange(0, 300); self.spin_upgrade_delay.setSuffix(" ms")
        self.dbl_preview_headroom = QDoubleSpinBox(self.perf_tab); self.dbl_preview_headroom.setRange(1.0, 1.2); self.dbl_preview_headroom.setSingleStep(0.05); self.dbl_preview_headroom.setDecimals(2)
        self.chk_disable_scaled_below_100 = QCheckBox("100% 이하에서도 원본 우선(프리뷰 비활성화)", self.perf_tab)
        self.chk_preserve_visual_size_on_dpr = QCheckBox("DPI 변경 시 보이는 크기 유지", self.perf_tab)
        form_pf.addRow("썸네일 프리페치", self.chk_prefetch_thumbs)
        form_pf.addRow("이웃 프리로드 반경", self.spin_preload_radius)
        form_pf.addRow("지도 프리페치", self.chk_prefetch_map)
        form_pf.addRow("프리로드 방향", self.combo_preload_direction)
        form_pf.addRow("프리로드 우선순위", self.spin_preload_priority)
        form_pf.addRow("프리로드 동시 작업 수", self.spin_preload_concurrency)
        form_pf.addRow("프리로드 재시도 횟수", self.spin_preload_retry)
        form_pf.addRow("프리로드 재시도 지연", self.spin_preload_retry_delay)
        form_pf.addRow("업그레이드 지연", self.spin_upgrade_delay)
        form_pf.addRow("프리뷰 여유 배율", self.dbl_preview_headroom)
        form_pf.addRow("100% 이하 프리뷰 비활성화", self.chk_disable_scaled_below_100)
        form_pf.addRow("DPI 변경 시 크기 유지", self.chk_preserve_visual_size_on_dpr)
        form_pf.addRow("원본 캐시 상한", self.spin_img_cache_mb)
        form_pf.addRow("스케일 캐시 상한", self.spin_scaled_cache_mb)
        form_pf.addRow("저메모리 시 축소 비율", self.spin_cache_auto_shrink_pct)
        form_pf.addRow("캐시 정리 주기", self.spin_cache_gc_interval)
        perf_layout.addLayout(form_pf)

        # 썸네일 캐시 옵션
        perf_layout.addWidget(QLabel("썸네일 캐시", self.perf_tab))
        self.spin_thumb_quality = QSpinBox(self.perf_tab); self.spin_thumb_quality.setRange(50, 100); self.spin_thumb_quality.setSuffix(" %")
        from PyQt6.QtWidgets import QLineEdit as _QLineEdit  # type: ignore[import]
        self.ed_thumb_dir = _QLineEdit(self.perf_tab)
        self.ed_thumb_dir.setPlaceholderText("기본 경로 사용 시 비워두세요")
        self.btn_thumb_dir = QPushButton("변경…", self.perf_tab)
        def _pick_thumb_dir():
            try:
                from PyQt6.QtWidgets import QFileDialog  # type: ignore[import]
                d = QFileDialog.getExistingDirectory(self, "썸네일 캐시 폴더 선택", self.ed_thumb_dir.text() or os.path.expanduser("~"))
                if d:
                    self.ed_thumb_dir.setText(d)
            except Exception:
                pass
        try:
            self.btn_thumb_dir.clicked.connect(_pick_thumb_dir)
        except Exception:
            pass
        row_thumb = QFormLayout()
        row_thumb.addRow("품질", self.spin_thumb_quality)
        from PyQt6.QtWidgets import QHBoxLayout as _HBox  # type: ignore[import]
        _h = _HBox(); _h.addWidget(self.ed_thumb_dir, 1); _h.addWidget(self.btn_thumb_dir)
        row_thumb.addRow("저장 위치", _h)
        perf_layout.addLayout(row_thumb)

        # 지능형 스케일 프리젠
        perf_layout.addWidget(QLabel("지능형 스케일 프리젠", self.perf_tab))
        self.chk_pregen_scales = QCheckBox("선호 배율 미리 생성", self.perf_tab)
        from PyQt6.QtWidgets import QLineEdit as _QLineEdit2  # type: ignore[import]
        self.ed_pregen_scales = _QLineEdit2(self.perf_tab)
        self.ed_pregen_scales.setPlaceholderText("예: 0.25,0.5,1.0,2.0")
        form_pregen = QFormLayout()
        form_pregen.addRow("활성화", self.chk_pregen_scales)
        form_pregen.addRow("배율 목록", self.ed_pregen_scales)
        perf_layout.addLayout(form_pregen)

        # 프리로드 시점 옵션
        perf_layout.addWidget(QLabel("프리로드 시점", self.perf_tab))
        self.chk_preload_idle_only = QCheckBox("유휴 시간에만 프리로드 실행", self.perf_tab)
        self.spin_prefetch_on_dir_enter = QSpinBox(self.perf_tab); self.spin_prefetch_on_dir_enter.setRange(0, 50); self.spin_prefetch_on_dir_enter.setSuffix(" 장")
        self.spin_slideshow_prefetch = QSpinBox(self.perf_tab); self.spin_slideshow_prefetch.setRange(0, 100); self.spin_slideshow_prefetch.setSuffix(" 장")
        form_pt = QFormLayout()
        form_pt.addRow("유휴 시 프리로드", self.chk_preload_idle_only)
        form_pt.addRow("디렉터리 진입 예열", self.spin_prefetch_on_dir_enter)
        form_pt.addRow("슬라이드쇼 시작 예열", self.spin_slideshow_prefetch)
        perf_layout.addLayout(form_pt)

        # 단축키 탭 제거
        self._keys_ready = False
        # 단축키 입력부(키 설정) 섹션 제거 유지 — 별도 탭/대화에서만 다루도록 고정

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
        # 회전 시 화면 중심 앵커 유지 여부
        self.chk_anchor_preserve = QCheckBox("회전 시 화면 중심 앵커 유지", self.view_tab)
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
        form_view.addRow("회전 중심 앵커 유지", self.chk_anchor_preserve)
        form_view.addRow("DPR 시각 크기 유지", self.chk_preserve_visual_dpr)
        view_layout.addLayout(form_view)

        # ----- 색상 관리 탭 -----
        self.color_tab = QWidget(self)
        self.tabs.addTab(self.color_tab, "색상")
        color_layout = QVBoxLayout(self.color_tab)
        try:
            color_layout.setContentsMargins(8, 8, 8, 8)
            color_layout.setSpacing(8)
        except Exception:
            pass
        self.chk_icc_ignore = QCheckBox("임베디드 ICC 무시", self.color_tab)
        self.combo_assumed = QComboBox(self.color_tab)
        self.combo_assumed.addItems(["sRGB", "Display P3", "Adobe RGB"])  # ICC 미탑재/무시 시 가정
        self.combo_target = QComboBox(self.color_tab)
        self.combo_target.addItems(["sRGB", "Display P3", "Adobe RGB"])   # 미리보기 타깃
        self.combo_fallback = QComboBox(self.color_tab)
        self.combo_fallback.addItems(["ignore", "force_sRGB"])  # 경고 UI는 보류
        self.chk_anim_convert = QCheckBox("애니메이션 프레임 sRGB 변환", self.color_tab)
        self.chk_thumb_convert = QCheckBox("썸네일 sRGB 변환", self.color_tab)
        form_color = QFormLayout()
        form_color.addRow("ICC 무시", self.chk_icc_ignore)
        form_color.addRow("ICC 없음 가정 색공간", self.combo_assumed)
        form_color.addRow("미리보기 타깃", self.combo_target)
        form_color.addRow("실패 시 폴백", self.combo_fallback)
        form_color.addRow("애니메이션 변환", self.chk_anim_convert)
        form_color.addRow("썸네일 변환", self.chk_thumb_convert)
        color_layout.addLayout(form_color)
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
        # 확인 버튼: 색상 설정 포함하여 전체 적용
        def _apply_all_and_accept():
            try:
                self._apply_color_settings()
            except Exception:
                pass
            try:
                # 기존 단축키 저장/검증 로직은 별도 _on_accept에 있음 → 호출 유지
                self._on_accept()
            except Exception:
                # 키 탭이 준비되지 않았으면 그냥 닫기
                try:
                    self.accept()
                except Exception:
                    pass
        buttons.accepted.connect(_apply_all_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _apply_values_from_viewer(self):
        viewer = self.parent() if hasattr(self, 'parent') else None
        if viewer is None:
            return
        # 색상 탭: 로드
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

    def _apply_color_settings(self):
        viewer = self.parent() if hasattr(self, 'parent') else None
        if viewer is None:
            return
        # 색상 탭: 저장
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
        # 이미지 서비스에도 즉시 반영
        try:
            if hasattr(viewer, 'image_service') and viewer.image_service is not None:
                svc = viewer.image_service
                svc._icc_ignore_embedded = bool(getattr(viewer, "_icc_ignore_embedded", False))
                svc._assumed_colorspace = str(getattr(viewer, "_assumed_colorspace", "sRGB"))
                svc._preview_target = str(getattr(viewer, "_preview_target", "sRGB"))
                svc._fallback_policy = str(getattr(viewer, "_fallback_policy", "ignore"))
        except Exception:
            pass
        try:
            viewer.save_settings()
        except Exception:
            pass

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

        # 스크롤 영역/레이아웃 구성 이후, 휠 가드용 필터 설치 준비
        try:
            self._wheel_guard_targets = []
        except Exception:
            self._wheel_guard_targets = []
        # 일반 탭 구성 마지막에 각 입력 위젯을 휠가드 대상으로 등록
        try:
            for w in [
                self.spin_recent_max,
                self.combo_startup_restore,
                self.chk_recent_auto_prune,
                self.chk_scan_after_open,
                self.chk_remember_last_dir,
                self.chk_anim_autoplay,
                self.chk_anim_loop,
                self.combo_sort_mode,
                self.combo_sort_name,
                self.chk_exclude_hidden,
                self.chk_wrap_ends,
                self.spin_nav_throttle,
                self.chk_film_center,
                self.combo_zoom_policy,
                self.chk_drop_allow_folder,
                self.chk_drop_parent_scan,
                self.chk_drop_overlay,
                self.chk_drop_confirm,
                self.spin_drop_threshold,
                self.chk_prefetch_thumbs,
                self.spin_preload_radius,
                self.chk_prefetch_map,
                self.chk_ai_auto,
                self.spin_ai_delay,
                self.chk_tiff_first_page,
            ]:
                if w:
                    try:
                        w.installEventFilter(self)
                        self._wheel_guard_targets.append(w)
                    except Exception:
                        pass
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
        # 색상 탭 값 먼저 반영
        try:
            self._apply_values_from_viewer()
        except Exception:
            pass
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
            self.spin_anim_overlay_opacity.setValue(0.6)
        # 세션/최근 로드
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
        # 제외 규칙 삭제됨 — 로드 없음
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
            self.chk_anchor_preserve.setChecked(bool(getattr(viewer, "_anchor_preserve_on_transform", True)))
        except Exception:
            self.chk_anchor_preserve.setChecked(True)
        try:
            self.chk_preserve_visual_dpr.setChecked(bool(getattr(viewer, "_preserve_visual_size_on_dpr_change", False)))
        except Exception:
            self.chk_preserve_visual_dpr.setChecked(False)
        # 드래그 앤 드롭 로드
        try:
            self.chk_drop_allow_folder.setChecked(bool(getattr(viewer, "_drop_allow_folder", False)))
        except Exception:
            self.chk_drop_allow_folder.setChecked(False)
        try:
            self.chk_drop_parent_scan.setChecked(bool(getattr(viewer, "_drop_use_parent_scan", True)))
        except Exception:
            self.chk_drop_parent_scan.setChecked(True)
        try:
            self.chk_drop_overlay.setChecked(bool(getattr(viewer, "_drop_show_overlay", True)))
        except Exception:
            self.chk_drop_overlay.setChecked(True)
        try:
            self.chk_drop_confirm.setChecked(bool(getattr(viewer, "_drop_confirm_over_threshold", True)))
        except Exception:
            self.chk_drop_confirm.setChecked(True)
        try:
            self.spin_drop_threshold.setValue(int(getattr(viewer, "_drop_large_threshold", 500)))
        except Exception:
            self.spin_drop_threshold.setValue(500)
        # 성능/프리페치 로드
        try:
            self.spin_upgrade_delay.setValue(int(getattr(viewer, "_fullres_upgrade_delay_ms", 120)))
        except Exception:
            self.spin_upgrade_delay.setValue(120)
        try:
            self.dbl_preview_headroom.setValue(float(getattr(viewer, "_preview_headroom", 1.0)))
        except Exception:
            self.dbl_preview_headroom.setValue(1.0)
        try:
            self.chk_disable_scaled_below_100.setChecked(bool(getattr(viewer, "_disable_scaled_cache_below_100", False)))
        except Exception:
            self.chk_disable_scaled_below_100.setChecked(False)
        try:
            self.chk_preserve_visual_size_on_dpr.setChecked(bool(getattr(viewer, "_preserve_visual_size_on_dpr_change", False)))
        except Exception:
            self.chk_preserve_visual_size_on_dpr.setChecked(False)
        try:
            self.chk_prefetch_thumbs.setChecked(bool(getattr(viewer, "_enable_thumb_prefetch", True)))
        except Exception:
            self.chk_prefetch_thumbs.setChecked(True)
        try:
            self.spin_preload_radius.setValue(int(getattr(viewer, "_preload_radius", 2)))
        except Exception:
            self.spin_preload_radius.setValue(2)
        try:
            self.chk_prefetch_map.setChecked(bool(getattr(viewer, "_enable_map_prefetch", True)))
        except Exception:
            self.chk_prefetch_map.setChecked(True)
        # 프리로드 방향/우선순위/동시 수/캐시 상한 로드
        try:
            dir_map = {"both":0, "forward":1, "backward":2}
            self.combo_preload_direction.setCurrentIndex(dir_map.get(str(getattr(viewer, "_preload_direction", "both")), 0))
        except Exception:
            self.combo_preload_direction.setCurrentIndex(0)
        try:
            self.spin_preload_priority.setValue(int(getattr(viewer, "_preload_priority", -1)))
        except Exception:
            self.spin_preload_priority.setValue(-1)
        try:
            self.spin_preload_concurrency.setValue(int(getattr(viewer, "_preload_max_concurrency", 0)))
        except Exception:
            self.spin_preload_concurrency.setValue(0)
        try:
            self.spin_preload_retry.setValue(int(getattr(viewer, "_preload_retry_count", 0)))
        except Exception:
            self.spin_preload_retry.setValue(0)
        try:
            self.spin_preload_retry_delay.setValue(int(getattr(viewer, "_preload_retry_delay_ms", 0)))
        except Exception:
            self.spin_preload_retry_delay.setValue(0)
        try:
            mb = int(max(1, int(getattr(viewer, "_img_cache_max_bytes", 256*1024*1024)) // (1024*1024)))
            self.spin_img_cache_mb.setValue(mb)
        except Exception:
            self.spin_img_cache_mb.setValue(256)
        try:
            mb2 = int(max(1, int(getattr(viewer, "_scaled_cache_max_bytes", 384*1024*1024)) // (1024*1024)))
            self.spin_scaled_cache_mb.setValue(mb2)
        except Exception:
            self.spin_scaled_cache_mb.setValue(384)
        try:
            self.spin_cache_auto_shrink_pct.setValue(int(getattr(viewer, "_cache_auto_shrink_pct", 50)))
        except Exception:
            self.spin_cache_auto_shrink_pct.setValue(50)
        try:
            self.spin_cache_gc_interval.setValue(int(getattr(viewer, "_cache_gc_interval_s", 0)))
        except Exception:
            self.spin_cache_gc_interval.setValue(0)
        # 썸네일 캐시
        try:
            self.spin_thumb_quality.setValue(int(getattr(viewer, "_thumb_cache_quality", 85)))
        except Exception:
            self.spin_thumb_quality.setValue(85)
        try:
            self.ed_thumb_dir.setText(str(getattr(viewer, "_thumb_cache_dir", "")) or "")
        except Exception:
            self.ed_thumb_dir.setText("")
        # 지능형 스케일 프리젠 로드
        try:
            self.chk_pregen_scales.setChecked(bool(getattr(viewer, "_pregen_scales_enabled", False)))
        except Exception:
            self.chk_pregen_scales.setChecked(False)
        try:
            arr = getattr(viewer, "_pregen_scales", [0.25, 0.5, 1.0, 2.0])
            if isinstance(arr, (list, tuple)):
                txt = ",".join([str(x) for x in arr])
            else:
                txt = "0.25,0.5,1.0,2.0"
            self.ed_pregen_scales.setText(txt)
        except Exception:
            self.ed_pregen_scales.setText("0.25,0.5,1.0,2.0")
        # 자동화 로드
        try:
            self.chk_ai_auto.setChecked(bool(getattr(viewer, "_auto_ai_on_open", False)))
        except Exception:
            self.chk_ai_auto.setChecked(False)
        try:
            self.spin_ai_delay.setValue(int(getattr(viewer, "_auto_ai_delay_ms", 0)))
        except Exception:
            self.spin_ai_delay.setValue(0)

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
            viewer._anim_keep_state_on_switch = bool(self.chk_anim_keep_state.isChecked())
        except Exception:
            pass
        try:
            viewer._anim_pause_on_unfocus = bool(self.chk_anim_pause_unfocus.isChecked())
        except Exception:
            pass
        try:
            viewer._anim_click_toggle = bool(self.chk_anim_click_toggle.isChecked())
        except Exception:
            pass
        try:
            viewer._anim_overlay_enabled = bool(self.chk_anim_overlay_enable.isChecked())
            viewer._anim_overlay_show_index = bool(self.chk_anim_overlay_show_index.isChecked())
            pos_idx = int(self.combo_anim_overlay_pos.currentIndex())
            viewer._anim_overlay_position = ("top-left" if pos_idx == 0 else ("top-right" if pos_idx == 1 else ("bottom-left" if pos_idx == 2 else "bottom-right")))
            viewer._anim_overlay_opacity = float(self.spin_anim_overlay_opacity.value())
        except Exception:
            pass
        # 세션/최근 저장
        try:
            pol_idx = int(self.combo_startup_restore.currentIndex())
            viewer._startup_restore_policy = ("always" if pol_idx == 0 else ("ask" if pol_idx == 1 else "never"))
        except Exception:
            pass
        try:
            viewer._recent_max_items = int(self.spin_recent_max.value())
        except Exception:
            pass
        # 제외 규칙 삭제됨 — 저장 없음
        try:
            is_explorer = (int(self.combo_sort_name.currentIndex()) == 0)
            viewer._dir_natural_sort = bool(is_explorer)
            # 탐색기 정렬이면 기준 강제 파일명
            if is_explorer:
                viewer._dir_sort_mode = "name"
            else:
                viewer._dir_sort_mode = ("metadata" if int(self.combo_sort_mode.currentIndex()) == 0 else "name")
        except Exception:
            pass
        # UI 상태(비활성화)는 즉시 반영
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
        # 드래그 앤 드롭 적용
        try:
            viewer._drop_allow_folder = bool(self.chk_drop_allow_folder.isChecked())
        except Exception:
            pass
        try:
            viewer._drop_use_parent_scan = bool(self.chk_drop_parent_scan.isChecked())
        except Exception:
            pass
        try:
            viewer._drop_show_overlay = bool(self.chk_drop_overlay.isChecked())
        except Exception:
            pass
        try:
            viewer._drop_confirm_over_threshold = bool(self.chk_drop_confirm.isChecked())
        except Exception:
            pass
        try:
            viewer._drop_large_threshold = int(self.spin_drop_threshold.value())
        except Exception:
            pass
        # 성능/프리페치 적용
        try:
            viewer._enable_thumb_prefetch = bool(self.chk_prefetch_thumbs.isChecked())
        except Exception:
            pass
        try:
            viewer._preload_radius = int(self.spin_preload_radius.value())
        except Exception:
            pass
        try:
            viewer._enable_map_prefetch = bool(self.chk_prefetch_map.isChecked())
        except Exception:
            pass
        # 프리로드/캐시 정책 적용
        try:
            idx = int(self.combo_preload_direction.currentIndex())
            viewer._preload_direction = ("both" if idx == 0 else ("forward" if idx == 1 else "backward"))
        except Exception:
            pass
        try:
            viewer._preload_priority = int(self.spin_preload_priority.value())
        except Exception:
            pass
        # 성능/프리뷰 정책 적용
        try:
            viewer._fullres_upgrade_delay_ms = int(self.spin_upgrade_delay.value())
        except Exception:
            pass
        try:
            viewer._preview_headroom = float(self.dbl_preview_headroom.value())
        except Exception:
            pass
        try:
            viewer._disable_scaled_cache_below_100 = bool(self.chk_disable_scaled_below_100.isChecked())
        except Exception:
            pass
        try:
            viewer._preserve_visual_size_on_dpr_change = bool(self.chk_preserve_visual_size_on_dpr.isChecked())
        except Exception:
            pass
        try:
            viewer._preload_max_concurrency = int(self.spin_preload_concurrency.value())
        except Exception:
            pass
        try:
            viewer._preload_retry_count = int(self.spin_preload_retry.value())
        except Exception:
            pass
        try:
            viewer._preload_retry_delay_ms = int(self.spin_preload_retry_delay.value())
        except Exception:
            pass
        try:
            viewer._preload_only_when_idle = bool(self.chk_preload_idle_only.isChecked())
        except Exception:
            pass
        try:
            viewer._prefetch_on_dir_enter = int(self.spin_prefetch_on_dir_enter.value())
        except Exception:
            pass
        try:
            viewer._slideshow_prefetch_count = int(self.spin_slideshow_prefetch.value())
        except Exception:
            pass
        try:
            viewer._img_cache_max_bytes = int(self.spin_img_cache_mb.value()) * 1024 * 1024
            viewer._scaled_cache_max_bytes = int(self.spin_scaled_cache_mb.value()) * 1024 * 1024
            if hasattr(viewer, "image_service") and viewer.image_service is not None:
                viewer.image_service.set_cache_limits(viewer._img_cache_max_bytes, viewer._scaled_cache_max_bytes)
        except Exception:
            pass
        try:
            viewer._cache_auto_shrink_pct = int(self.spin_cache_auto_shrink_pct.value())
            viewer._cache_gc_interval_s = int(self.spin_cache_gc_interval.value())
        except Exception:
            pass
        try:
            viewer._thumb_cache_quality = int(self.spin_thumb_quality.value())
            viewer._thumb_cache_dir = str(self.ed_thumb_dir.text()).strip()
            # 필름스트립이 생성되었다면 즉시 적용
            if hasattr(viewer, 'filmstrip') and viewer.filmstrip is not None and getattr(viewer.filmstrip, '_cache', None) is not None:
                try:
                    viewer.filmstrip._cache.quality = int(viewer._thumb_cache_quality)
                    if viewer._thumb_cache_dir:
                        viewer.filmstrip._cache.root = viewer._thumb_cache_dir
                except Exception:
                    pass
        except Exception:
            pass
        # 자동화 적용
        # 지능형 스케일 프리젠 적용
        try:
            viewer._pregen_scales_enabled = bool(self.chk_pregen_scales.isChecked())
            raw = str(self.ed_pregen_scales.text()).strip()
            arr = []
            for p in [t.strip() for t in raw.split(',') if t.strip()]:
                try:
                    arr.append(float(p))
                except Exception:
                    pass
            if not arr:
                arr = [0.25, 0.5, 1.0, 2.0]
            viewer._pregen_scales = arr
        except Exception:
            pass
        try:
            viewer._auto_ai_on_open = bool(self.chk_ai_auto.isChecked())
        except Exception:
            pass
        try:
            viewer._auto_ai_delay_ms = int(self.spin_ai_delay.value())
        except Exception:
            pass

    def _on_sort_name_changed(self):
        try:
            is_explorer = (self.combo_sort_name.currentIndex() == 0)
            # 윈도우 탐색기 정렬 선택 시 자동으로 정렬 기준을 파일명으로 강제하고 비활성화
            if is_explorer:
                try:
                    if int(self.combo_sort_mode.currentIndex()) != 1:
                        self.combo_sort_mode.setCurrentIndex(1)  # 파일명
                except Exception:
                    self.combo_sort_mode.setCurrentIndex(1)
                self.combo_sort_mode.setEnabled(False)
            else:
                self.combo_sort_mode.setEnabled(True)
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
            # 성능/프리뷰 기본값
            self.spin_upgrade_delay.setValue(120)
            self.dbl_preview_headroom.setValue(1.0)
            self.chk_disable_scaled_below_100.setChecked(False)
            self.chk_preserve_visual_size_on_dpr.setChecked(False)
            # 캐시/프리페치 기본값(이미 로드된 경우 유지)
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
            from PyQt6.QtCore import QEvent  # type: ignore
            et = event.type()
            # 키 시퀀스 에디터 기존 로직 유지
            if isinstance(obj, QKeySequenceEdit):
                if et == QEvent.Type.FocusIn:
                    for ed in getattr(self, "_key_editors", []) or []:
                        if ed is not obj and ed.hasFocus():
                            try:
                                ed.clearFocus()
                            except Exception:
                                pass
                elif et == QEvent.Type.KeyPress:
                    key = getattr(event, 'key', None)
                    if key and int(key()) in (0x01000003, 0x01000007):  # Backspace/Delete
                        obj.setKeySequence(QKeySequence())
                        meta = getattr(self, "_editor_meta", {}).get(obj, None)
                        if meta is not None:
                            self._on_key_changed(obj, meta.get("defaults", []), int(meta.get("row", 0)))
                        return True
                return super().eventFilter(obj, event)
            # 휠 가드: 포커스 없는 경우 스핀/콤보/체크는 값 변경 금지
            if et == QEvent.Type.Wheel:
                from PyQt6.QtWidgets import QAbstractSpinBox, QComboBox, QCheckBox  # type: ignore
                if isinstance(obj, (QAbstractSpinBox, QComboBox, QCheckBox)):
                    if not obj.hasFocus():
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


