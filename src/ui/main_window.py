import os
import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QApplication, QMainWindow, QLabel, QSizePolicy, QMenu  # type: ignore[import]
from PyQt6.QtCore import QTimer, Qt, QSettings, QPointF, QEvent  # type: ignore[import]
from PyQt6.QtGui import QKeySequence, QShortcut, QImage, QAction, QPixmap, QMovie, QColorSpace  # type: ignore[import]

from .image_view import ImageView
from ..utils.file_utils import open_file_dialog_util, cleanup_leftover_temp_and_backup
from ..utils.delete_utils import move_to_trash_windows
from ..storage.mru_store import normalize_path, update_mru
from ..dnd.dnd_handlers import handle_dropped_files, urls_to_local_files
from .fullscreen_controller import enter_fullscreen as fs_enter_fullscreen, exit_fullscreen as fs_exit_fullscreen
from .menu_builder import rebuild_recent_menu as build_recent_menu
from ..shortcuts.shortcuts import setup_shortcuts as setup_shortcuts_ext
from ..shortcuts.shortcuts_manager import apply_shortcuts as apply_shortcuts_ext
from ..services.session_service import save_last_session as save_session_ext, restore_last_session as restore_session_ext
from ..storage.settings_store import load_settings as load_settings_ext, save_settings as save_settings_ext
from ..utils.navigation import show_prev_image as nav_show_prev_image, show_next_image as nav_show_next_image, load_image_at_current_index as nav_load_image_at_current_index, update_button_states as nav_update_button_states
from .title_status import update_window_title as ts_update_window_title, update_status_left as ts_update_status_left, update_status_right as ts_update_status_right
from ..dnd.dnd_setup import setup_global_dnd as setup_global_dnd_ext, enable_dnd as enable_dnd_ext
from ..services.image_service import ImageService
from .settings_dialog import SettingsDialog
from .shortcuts_help_dialog import ShortcutsHelpDialog
from ..utils.logging_setup import get_logger, get_log_dir, export_logs_zip, suggest_logs_zip_name, open_logs_folder

class JusawiViewer(QMainWindow):
    def __init__(self, skip_session_restore: bool = False):
        super().__init__()
        # 세션 복원 스킵 여부(명령줄로 파일/폴더가 지정된 경우 사용)
        self._skip_session_restore = bool(skip_session_restore)
        self.setWindowTitle("Jusawi")
        self.log = get_logger("ui.JusawiViewer")

        self.current_image_path = None
        self.image_files_in_dir = []
        self.current_image_index = -1
        self.load_successful = False
        # 줌 상태(레거시 변수는 유지하되, ImageView가 관리)
        self.scale_factor = 1.0
        self.fit_mode = True
        self.min_scale = 0.01
        self.max_scale = 16.0
        
        # 전체화면 및 슬라이드쇼 상태 관리
        self.is_fullscreen = False
        self.is_slideshow_active = False
        self.button_layout = None  # 나중에 설정
        self.previous_window_state = None  # 전체화면 이전 상태 저장

        # 상태 캐시(우측 상태 표시용)
        self._last_cursor_x = 0
        self._last_cursor_y = 0
        self._last_scale = 1.0
        self._last_view_mode = 'fit'
        self._last_center = QPointF(0.0, 0.0)

        # 편집/변환 상태
        self._tf_rotation = 0  # 0/90/180/270
        self._tf_flip_h = False
        self._tf_flip_v = False
        self._is_dirty = False
        self._save_policy = 'discard'  # 'discard' | 'ask' | 'overwrite' | 'save_as'
        self._jpeg_quality = 95
        # 편집 히스토리(Undo/Redo)
        self._history_undo = []  # list[tuple[int,bool,bool]]
        self._history_redo = []  # list[tuple[int,bool,bool]]
        # 애니메이션 재생 상태
        self._anim_is_playing = False
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(100)  # 기본 10fps
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._movie = None  # type: QMovie | None
        # 옵션: QMovie 프레임도 sRGB로 변환(성능 비용 존재). 기본 활성화
        self._convert_movie_frames_to_srgb = True

        # 설정 저장(QSettings)
        self.settings = QSettings("Jusawi", "Jusawi")
        self.recent_files = []  # list[dict]
        self.recent_folders = []  # list[dict]
        self.last_open_dir = ""

        # QMainWindow의 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # 중앙 영역 배경을 #373737로 통일
        central_widget.setStyleSheet("background-color: #373737;")
        # Drag & Drop 허용 (초기 상태 포함 창 어디서나 동작하도록 중앙/뷰포트에도 적용)
        self.setAcceptDrops(True)
        central_widget.setAcceptDrops(True)
        central_widget.installEventFilter(self)

        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self._normal_margins = (5, 5, 5, 5)

        # ImageView (QGraphicsView 기반)
        self.image_display_area = ImageView(central_widget)
        self.image_display_area.scaleChanged.connect(self.on_scale_changed)
        self.image_display_area.cursorPosChanged.connect(self.on_cursor_pos_changed)
        # 명시적 min/max 스케일 설정
        self.image_display_area.set_min_max_scale(self.min_scale, self.max_scale)
        # ImageView 및 내부 뷰포트에도 DnD 허용 및 필터 설치
        self.image_display_area.setAcceptDrops(True)
        try:
            self.image_display_area.viewport().setAcceptDrops(True)
            self.image_display_area.viewport().installEventFilter(self)
        except Exception:
            pass
        self.image_display_area.installEventFilter(self)
        self.main_layout.addWidget(self.image_display_area, 1)

        # 이미지 서비스
        self.image_service = ImageService(self)
        self.image_service.loaded.connect(self._on_image_loaded)
        # 마지막 DPR 기억(배율 일관성 유지용)
        try:
            self._last_dpr = float(self.image_display_area.viewport().devicePixelRatioF())
        except Exception:
            self._last_dpr = 1.0
        # 자유 줌 상태에서 DPR 변경 시 배율(%)을 그대로 유지: True면 시각 크기 보존(배율 변함), False면 배율 고정
        # 사진 뷰어 UX 기준: 배율 표시는 불변이 더 직관적 -> 기본 False
        self._preserve_visual_size_on_dpr_change = False
        # DPR 전환 가드 및 해제 타이머(중복 재적용/재디바운스 방지)
        self._in_dpr_transition = False
        self._dpr_guard_timer = QTimer(self)
        self._dpr_guard_timer.setSingleShot(True)
        self._dpr_guard_timer.timeout.connect(lambda: setattr(self, "_in_dpr_transition", False))
        # 썸네일(다운샘플) 표시 후 원본으로 1회 업그레이드 타이머
        self._fullres_upgrade_timer = QTimer(self)
        self._fullres_upgrade_timer.setSingleShot(True)
        self._fullres_upgrade_timer.timeout.connect(self._upgrade_to_fullres_if_needed)
        # 사용자 요청: 100% 이하 배율에서 썸네일 캐싱/표시를 비활성화하고 항상 원본을 사용
        self._disable_scaled_cache_below_100 = True
        # DPR/모니터 변경 시 재적용 트리거 설정 (표시 후에도 보장되도록 별도 보조 메서드 사용)
        self._screen_signal_connected = False
        try:
            self._ensure_screen_signal_connected()
        except Exception:
            pass
        # 뷰포트 스케일 적용 디바운스 타이머
        self._scale_apply_timer = QTimer(self)
        self._scale_apply_timer.setSingleShot(True)
        self._scale_apply_timer.setInterval(30)
        self._scale_apply_timer.timeout.connect(self._apply_scaled_pixmap_now)
        self._scale_apply_delay_ms = 30
        # 원본 풀해상도 이미지 보관(저장/고배율 표시용)
        self._fullres_image = None
        # 프리로드 설정(다음/이전 1장씩)
        self._preload_radius = 1

        self.button_layout = QHBoxLayout()
        self.open_button = QPushButton("열기")
        self.open_button.clicked.connect(self.open_file)
        # 최근 메뉴를 별도 버튼에 연결 + 로그 메뉴 추가
        self.recent_menu = QMenu(self)
        self.recent_button = QPushButton("최근 파일")
        self.recent_button.setMenu(self.recent_menu)
        self.log_menu = QMenu(self)
        self.log_button = QPushButton("로그")
        self.log_button.setMenu(self.log_menu)

        # 설정 버튼
        self.settings_button = QPushButton("설정")
        self.settings_button.clicked.connect(self.open_settings_dialog)

        # 새로: 전체화면 버튼
        self.fullscreen_button = QPushButton("전체화면")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

        # 줌/내비 컨트롤 버튼
        self.prev_button = QPushButton("이전")
        self.next_button = QPushButton("다음")
        self.prev_button.clicked.connect(self.show_prev_image)
        self.next_button.clicked.connect(self.show_next_image)
        self.zoom_out_button = QPushButton("축소")
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.fit_button = QPushButton("100%")
        self.fit_button.clicked.connect(self.reset_to_100)
        self.zoom_in_button = QPushButton("확대")
        self.zoom_in_button.clicked.connect(self.zoom_in)

        # (요청) 애니메이션 제어 버튼 제거

        # 회전 버튼(좌/우 90°만) 생성 (레이아웃에 추가하기 전에 생성해야 함)
        self.rotate_left_button = QPushButton("↶90°")
        self.rotate_right_button = QPushButton("↷90°")
        self.rotate_left_button.clicked.connect(self.rotate_ccw_90)
        self.rotate_right_button.clicked.connect(self.rotate_cw_90)

        # 상단 버튼 텍스트 색 적용 및 창 크기에 비례하지 않도록 고정 크기 정책 설정
        button_style = "color: #EAEAEA;"
        for btn in [
            self.open_button,
            self.recent_button,
            self.settings_button,
            self.fullscreen_button,
            self.prev_button,
            self.next_button,
            self.zoom_out_button,
            self.fit_button,
            self.zoom_in_button,
        ]:
            btn.setStyleSheet(button_style)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 버튼 순서: 열기 최근 전체화면 이전 다음 축소 100% 확대 회전 좌/우 ... 설정(맨 오른쪽)
        self.button_layout.addWidget(self.open_button)
        self.button_layout.addWidget(self.recent_button)
        self.button_layout.addWidget(self.fullscreen_button)
        self.button_layout.addWidget(self.prev_button)
        self.button_layout.addWidget(self.next_button)
        self.button_layout.addWidget(self.zoom_out_button)
        self.button_layout.addWidget(self.fit_button)
        self.button_layout.addWidget(self.zoom_in_button)
        # (제거됨)
        # 회전 버튼(확대 바로 옆)
        self.button_layout.addWidget(self.rotate_left_button)
        self.button_layout.addWidget(self.rotate_right_button)
        self.button_layout.addWidget(self.log_button)
        # 남는 공간을 스트레치로 채운 후 설정 버튼을 맨 오른쪽에 배치
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.settings_button)

        # 버튼 바 컨테이너(투명 배경 유지)
        self.button_bar = QWidget()
        self.button_bar.setStyleSheet("background-color: transparent; QPushButton { color: #EAEAEA; }")
        self.button_bar.setLayout(self.button_layout)
        self.main_layout.insertWidget(0, self.button_bar)

        # 회전 버튼은 위에서 생성됨

        # 상태바: 좌측/우측 구성
        self.status_left_label = QLabel("", self)
        self.status_right_label = QLabel("", self)
        self.status_left_label.setStyleSheet("color: #EAEAEA;")
        self.status_right_label.setStyleSheet("color: #EAEAEA;")
        # 좌측: addWidget, 우측: addPermanentWidget
        self.statusBar().addWidget(self.status_left_label, 1)
        self.statusBar().addPermanentWidget(self.status_right_label)
        # 상태바 배경/경계/텍스트 색상 통일 및 가독성 향상
        self.statusBar().setStyleSheet(
            "QStatusBar { background-color: #373737; border-top: 1px solid #373737; color: #EAEAEA; } "
            "QStatusBar QLabel { color: #EAEAEA; } "
            "QStatusBar::item { border: 0px; }"
        )
        # 진행 표시 위젯(라이트): 상태바 우측에 임시 배치
        try:
            from PyQt6.QtWidgets import QProgressBar
            self._progress = QProgressBar(self)
            self._progress.setFixedWidth(160)
            self._progress.setRange(0, 100)
            self._progress.setVisible(False)
            self._cancel_btn = QPushButton("취소", self)
            self._cancel_btn.setVisible(False)
            self._cancel_btn.clicked.connect(lambda: getattr(self.image_service, "cancel_save", lambda: None)())
            self.statusBar().addPermanentWidget(self._progress)
            self.statusBar().addPermanentWidget(self._cancel_btn)
        except Exception:
            self._progress = None
            self._cancel_btn = None
        # 상태바도 DnD 허용 및 필터 설치
        try:
            self.statusBar().setAcceptDrops(True)
            self.statusBar().installEventFilter(self)
            self.status_left_label.setAcceptDrops(True)
            self.status_left_label.installEventFilter(self)
            self.status_right_label.setAcceptDrops(True)
            self.status_right_label.installEventFilter(self)
        except Exception:
            pass
        self.update_status_left()
        self.update_status_right()

        # 키보드 단축키 설정
        self.setup_shortcuts()
        # (요청) 스페이스바로 애니메이션 재생/일시정지 토글
        try:
            self.anim_space_shortcut = QShortcut(QKeySequence("Space"), self)
            self.anim_space_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            self.anim_space_shortcut.activated.connect(self.anim_toggle_play)
        except Exception:
            pass
        
        # 이미지 라벨에 초기 포커스 설정
        self.image_display_area.setFocus()
        
        self.update_button_states()

        # 전역 DnD 지원: 주요 위젯에 일괄 적용
        self._setup_global_dnd()

        # 전체화면 진입 전 스타일 복원용 변수
        self._stylesheet_before_fullscreen = None

        # 토스트 비활성화: 상태바/다이얼로그만 사용
        self.toast = None

        # 설정 로드 및 최근/세션 복원
        self.load_settings()
        self.rebuild_recent_menu()
        if not getattr(self, "_skip_session_restore", False):
            self.restore_last_session()
        # 남은 임시/백업 파일 정리 (최근 폴더 기준, 실패 무시)
        try:
            if self.last_open_dir and os.path.isdir(self.last_open_dir):
                cleanup_leftover_temp_and_backup(self.last_open_dir)
        except Exception:
            pass
        # UI 환경 설정 적용
        try:
            self._apply_ui_theme_and_spacing()
            self._preferred_view_mode = getattr(self, "_default_view_mode", 'fit')
        except Exception:
            self._preferred_view_mode = 'fit'
        # 배타 포커스를 위한 전역 단축키 관리
        self._global_shortcuts_enabled = True

    def clamp(self, value, min_v, max_v):
        return max(min_v, min(value, max_v))

    def _enable_dnd_on(self, widget):
        enable_dnd_ext(widget, self)

    def _setup_global_dnd(self):
        setup_global_dnd_ext(self)

    def _set_global_shortcuts_enabled(self, enabled: bool) -> None:
        self._global_shortcuts_enabled = bool(enabled)
        # ImageView 내부 QShortcut + shortcuts_manager에서 등록된 단축키 모두 대상
        try:
            for sc in getattr(self, "_shortcuts", []) or []:
                try:
                    sc.setEnabled(self._global_shortcuts_enabled)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self, "anim_space_shortcut") and self.anim_space_shortcut:
                self.anim_space_shortcut.setEnabled(self._global_shortcuts_enabled)
        except Exception:
            pass

    # ----- Undo/Redo 히스토리 -----
    def _capture_state(self):
        return (int(self._tf_rotation) % 360, bool(self._tf_flip_h), bool(self._tf_flip_v))

    def _restore_state(self, state) -> None:
        try:
            rot, fh, fv = state
            self._tf_rotation = int(rot) % 360
            self._tf_flip_h = bool(fh)
            self._tf_flip_v = bool(fv)
            self._apply_transform_to_view()
            self._mark_dirty(True)
            if getattr(self.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
                self.image_display_area.apply_current_view_mode()
        except Exception:
            pass

    def _history_push(self) -> None:
        try:
            self._history_undo.append(self._capture_state())
            self._history_redo.clear()
        except Exception:
            pass

    def undo_action(self) -> None:
        if not self.load_successful:
            return
        if not self._history_undo:
            return
        try:
            cur = self._capture_state()
            prev = self._history_undo.pop()
            self._history_redo.append(cur)
            self._restore_state(prev)
        except Exception:
            pass

    def redo_action(self) -> None:
        if not self.load_successful:
            return
        if not self._history_redo:
            return
        try:
            cur = self._capture_state()
            nxt = self._history_redo.pop()
            self._history_undo.append(cur)
            self._restore_state(nxt)
        except Exception:
            pass

    # Settings: 저장/로드
    def load_settings(self):
        load_settings_ext(self)

    def save_settings(self):
        save_settings_ext(self)

    # 최근 항목 유틸은 mru_store로 분리됨

    def rebuild_recent_menu(self):
        build_recent_menu(self)
        # 로그 메뉴 구성
        try:
            self.log_menu.clear()
            act_open = QAction("로그 폴더 열기", self)
            act_open.triggered.connect(self._open_logs_folder)
            self.log_menu.addAction(act_open)
            act_export = QAction("로그 내보내기(.zip)", self)
            act_export.triggered.connect(self._export_logs_zip)
            self.log_menu.addAction(act_export)
        except Exception:
            pass

    def _open_recent_folder(self, dir_path: str):
        if not dir_path or not os.path.isdir(dir_path):
            self.statusBar().showMessage("폴더가 존재하지 않습니다.", 3000)
            # 존재하지 않는 항목은 목록에서 제거
            self.recent_folders = [it for it in self.recent_folders if normalize_path(it.get("path","")) != normalize_path(dir_path)]
            self.save_settings()
            self.rebuild_recent_menu()
            return
        self.scan_directory(dir_path)
        if 0 <= self.current_image_index < len(self.image_files_in_dir):
            self.load_image(self.image_files_in_dir[self.current_image_index])
        else:
            self.statusBar().showMessage("폴더에 표시할 이미지가 없습니다.", 3000)

    def clear_recent(self):
        self.recent_files = []
        self.recent_folders = []
        self.save_settings()
        self.rebuild_recent_menu()

    # 로그: 폴더 열기/ZIP 내보내기
    def _open_logs_folder(self):
        ok, err = open_logs_folder()
        try:
            if ok:
                self.statusBar().showMessage("로그 폴더를 열었습니다.", 2000)
            else:
                self.statusBar().showMessage(err or "로그 폴더를 열 수 없습니다.", 3000)
        except Exception:
            pass

    def _export_logs_zip(self):
        try:
            from PyQt6.QtWidgets import QFileDialog
            default_name = suggest_logs_zip_name()
            dest, _ = QFileDialog.getSaveFileName(self, "로그 내보내기", default_name, "Zip Files (*.zip)")
        except Exception:
            dest = ""
        if not dest:
            return
        ok, err = export_logs_zip(dest)
        try:
            if ok:
                self.statusBar().showMessage("로그를 내보냈습니다.", 2000)
            else:
                self.statusBar().showMessage(err or "로그 내보내기에 실패했습니다.", 3000)
        except Exception:
            pass

    # Drag & Drop 지원: 유틸
    def _handle_dropped_files(self, files):
        handle_dropped_files(self, files)

    def _handle_dropped_folders(self, folders):
        if not folders:
            self.statusBar().showMessage("폴더가 없습니다.", 3000)
            return
        dir_path = folders[0]
        self.scan_directory(dir_path)
        if 0 <= self.current_image_index < len(self.image_files_in_dir):
            self.load_image(self.image_files_in_dir[self.current_image_index])
        else:
            self.statusBar().showMessage("폴더에 표시할 이미지가 없습니다.", 3000)
        # 최근 폴더 업데이트 제거
        try:
            pass
        except Exception:
            pass

    # Drag & Drop 이벤트 핸들러
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        paths = urls_to_local_files(urls)
        if not paths:
            event.ignore()
            return
        files = [p for p in paths if os.path.isfile(p)]
        if files:
            self._handle_dropped_files(files)
        event.acceptProposedAction()

    # 상태 관련 계산 유틸은 status_utils로 분리됨

    def update_status_left(self):
        ts_update_status_left(self)

    def update_status_right(self):
        ts_update_status_right(self)

    def on_scale_changed(self, scale: float):
        self._last_scale = scale
        self.update_status_right()
        # 디바운스 후 스케일별 다운샘플 적용
        try:
            if getattr(self, "_in_dpr_transition", False):
                return
            self._scale_apply_timer.start(getattr(self, "_scale_apply_delay_ms", 30))
        except Exception:
            pass

    def on_cursor_pos_changed(self, x: int, y: int):
        self._last_cursor_x = x
        self._last_cursor_y = y
        self.update_status_right()

    # ----- 애니메이션 컨트롤 -----
    def _is_current_file_animation(self) -> bool:
        try:
            if not self.current_image_path:
                return False
            is_anim, _ = self.image_service.probe_animation(self.current_image_path)
            return bool(is_anim)
        except Exception:
            return False

    def anim_prev_frame(self):
        if not self._is_current_file_animation():
            return
        try:
            cur = getattr(self.image_display_area, "_current_frame_index", 0)
            total = getattr(self.image_display_area, "_total_frames", -1)
            new_index = max(0, cur - 1)
            img, ok, err = self.image_service.load_frame(self.current_image_path, new_index)
            if ok and img and not img.isNull():
                self.image_display_area.setPixmap(QPixmap.fromImage(img))
                self.image_display_area.set_animation_state(True, new_index, total)
        except Exception:
            pass

    def anim_next_frame(self):
        if not self._is_current_file_animation():
            return
        try:
            cur = getattr(self.image_display_area, "_current_frame_index", 0)
            total = getattr(self.image_display_area, "_total_frames", -1)
            max_index = (total - 1) if isinstance(total, int) and total > 0 else (cur + 1)
            new_index = min(max_index, cur + 1)
            img, ok, err = self.image_service.load_frame(self.current_image_path, new_index)
            if ok and img and not img.isNull():
                self.image_display_area.setPixmap(QPixmap.fromImage(img))
                self.image_display_area.set_animation_state(True, new_index, total)
        except Exception:
            pass

    def anim_toggle_play(self):
        if not self._is_current_file_animation():
            return
        try:
            # QMovie 우선 사용
            if self._movie:
                if self._movie.state() == QMovie.MovieState.Running:
                    self._movie.setPaused(True)
                    self._anim_is_playing = False
                elif self._movie.state() == QMovie.MovieState.Paused:
                    self._movie.setPaused(False)
                    self._anim_is_playing = True
                else:
                    self._movie.start()
                    self._anim_is_playing = True
            else:
                # 폴백: 수동 타이머
                self._anim_is_playing = not self._anim_is_playing
                if self._anim_is_playing:
                    self._anim_timer.start()
                else:
                    self._anim_timer.stop()
        except Exception:
            pass

    def _on_anim_tick(self):
        # QMovie 사용 중이면 타이머 경로는 비활성화
        if getattr(self, "_movie", None):
            return
        if not self._is_current_file_animation():
            self._anim_timer.stop()
            self._anim_is_playing = False
            return
        try:
            cur = getattr(self.image_display_area, "_current_frame_index", 0)
            total = getattr(self.image_display_area, "_total_frames", -1)
            # 서비스 캐시 기반으로 안전 래핑
            if isinstance(total, int) and total > 1:
                next_index = (cur + 1) % total
            else:
                # total 미상일 경우 서비스가 내부 래핑 처리
                next_index = cur + 1
            img, ok, err = self.image_service.load_frame(self.current_image_path, next_index)
            if ok and img and not img.isNull():
                # 프레임 교체는 경량 경로 사용
                self.image_display_area.updatePixmapFrame(QPixmap.fromImage(img))
                # total이 미상이면 probe로 갱신 시도
                if not (isinstance(total, int) and total > 0):
                    try:
                        is_anim, fc = self.image_service.probe_animation(self.current_image_path)
                        total = fc if (is_anim and isinstance(fc, int)) else -1
                    except Exception:
                        total = -1
                self.image_display_area.set_animation_state(True, next_index, total)
        except Exception:
            pass

    def _on_movie_frame(self, frame_index: int):
        try:
            if not self._movie:
                return
            pm = self._movie.currentPixmap()
            if pm and not pm.isNull():
                if getattr(self, "_convert_movie_frames_to_srgb", False):
                    try:
                        img = pm.toImage()
                        cs = img.colorSpace()
                        srgb = QColorSpace(QColorSpace.NamedColorSpace.SRgb)
                        if cs.isValid() and cs != srgb:
                            img = img.convertToColorSpace(srgb)
                        pm = QPixmap.fromImage(img)
                    except Exception:
                        pass
                self.image_display_area.updatePixmapFrame(pm)
                total = self._movie.frameCount()
                self.image_display_area.set_animation_state(True, frame_index, total)
        except Exception:
            pass

    # 세션 저장/복원
    def save_last_session(self):
        save_session_ext(self)

    def restore_last_session(self):
        restore_session_ext(self)

    def reset_zoom(self, fit=True):
        self.fit_mode = bool(fit)
        if self.fit_mode:
            self.image_display_area.fit_to_window()
        else:
            self.scale_factor = 1.0
        self.update_button_states()

    def fit_to_window(self):
        if not self.load_successful:
            return
        self.image_display_area.fit_to_window()
        self.update_button_states()

    def fit_to_width(self):
        if not self.load_successful:
            return
        self.image_display_area.fit_to_width()
        self.update_button_states()

    def fit_to_height(self):
        if not self.load_successful:
            return
        self.image_display_area.fit_to_height()
        self.update_button_states()

    def zoom_in(self):
        if not self.load_successful:
            return
        self.image_display_area.zoom_in()
        self.update_button_states()

    def zoom_out(self):
        if not self.load_successful:
            return
        self.image_display_area.zoom_out()
        self.update_button_states()

    def on_wheel_zoom(self, delta_y, ctrl, vp_anchor):
        # ImageView가 휠 이벤트를 처리하므로 이 메서드는 사용하지 않습니다.
        pass

    def update_window_title(self, file_path=None):
        """창 제목 업데이트"""
        ts_update_window_title(self, file_path)

    # ----- 변환 상태 관리 -----
    def _apply_transform_to_view(self):
        try:
            self.image_display_area.set_transform_state(self._tf_rotation, self._tf_flip_h, self._tf_flip_v)
        except Exception:
            pass
        self.update_status_right()

    def _mark_dirty(self, dirty: bool = True):
        self._is_dirty = bool(dirty)
        self.update_window_title(self.current_image_path)
        self.update_status_right()

    def get_transform_status_text(self) -> str:
        parts = []
        parts.append(f"{int(self._tf_rotation)}°")
        if self._tf_flip_h:
            parts.append("H")
        if self._tf_flip_v:
            parts.append("V")
        return " ".join(parts)

    def rotate_cw_90(self):
        if not self.load_successful:
            return
        self._history_push()
        self._tf_rotation = (self._tf_rotation + 90) % 360
        self._apply_transform_to_view()
        self._mark_dirty(True)
        # 화면 맞춤 모드일 경우 재-맞춤
        if getattr(self.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
            self.image_display_area.apply_current_view_mode()

    def rotate_ccw_90(self):
        if not self.load_successful:
            return
        self._history_push()
        self._tf_rotation = (self._tf_rotation - 90) % 360
        self._apply_transform_to_view()
        self._mark_dirty(True)
        if getattr(self.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
            self.image_display_area.apply_current_view_mode()

    def rotate_180(self):
        if not self.load_successful:
            return
        self._history_push()
        self._tf_rotation = (self._tf_rotation + 180) % 360
        self._apply_transform_to_view()
        self._mark_dirty(True)
        if getattr(self.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
            self.image_display_area.apply_current_view_mode()

    def flip_horizontal(self):
        if not self.load_successful:
            return
        self._history_push()
        self._tf_flip_h = not self._tf_flip_h
        self._apply_transform_to_view()
        self._mark_dirty(True)
        if getattr(self.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
            self.image_display_area.apply_current_view_mode()

    def flip_vertical(self):
        if not self.load_successful:
            return
        self._history_push()
        self._tf_flip_v = not self._tf_flip_v
        self._apply_transform_to_view()
        self._mark_dirty(True)
        if getattr(self.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
            self.image_display_area.apply_current_view_mode()

    def reset_transform_state(self):
        # 제거된 기능 (더 이상 사용하지 않음)
        pass

    # ImageService 콜백/적용
    def _on_image_loaded(self, path: str, img: QImage, success: bool, error: str):
        # 현재는 동기 로딩만 사용하므로 호출되지 않음
        if not success:
            return
        self._apply_loaded_image(path, img, source='async')

    def _apply_loaded_image(self, path: str, img: QImage, source: str):
        pixmap = QPixmap.fromImage(img)
        self.image_display_area.setPixmap(pixmap)
        # 풀해상도 보관
        try:
            self._fullres_image = img
            # 원본 자연 크기를 뷰에 전달(썸네일 표시 중에도 좌표계 일관)
            try:
                self.image_display_area._natural_width = int(img.width())
                self.image_display_area._natural_height = int(img.height())
            except Exception:
                pass
        except Exception:
            self._fullres_image = None
        # 기존 QMovie 정리
        try:
            if getattr(self, "_movie", None):
                try:
                    self._movie.stop()
                except Exception:
                    pass
                self._movie.deleteLater()
        except Exception:
            pass
        self._movie = None
        # 애니메이션 여부/프레임 수를 탐지하여 상태 반영(기본: 정지)
        try:
            is_anim, frame_count = self.image_service.probe_animation(path)
            self.image_display_area.set_animation_state(is_anim, current_index=0, total_frames=frame_count)
            if is_anim:
                try:
                    mv = QMovie(path)
                    mv.setCacheMode(QMovie.CacheMode.CacheAll)
                    try:
                        mv.jumpToFrame(0)
                    except Exception:
                        pass
                    mv.frameChanged.connect(self._on_movie_frame)
                    self._movie = mv
                    # 자동 재생 활성화
                    try:
                        self._anim_timer.stop()
                    except Exception:
                        pass
                    try:
                        self._movie.start()
                        self._anim_is_playing = True
                    except Exception:
                        self._anim_is_playing = False
                except Exception:
                    self._movie = None
                    self._anim_is_playing = False
            else:
                # 비애니메이션 파일은 재생 상태 해제
                self._anim_is_playing = False
        except Exception:
            try:
                self.image_display_area.set_animation_state(False)
            except Exception:
                pass
        try:
            self.log.info("apply_loaded | file=%s | source=%s | anim=%s", os.path.basename(path), source, bool(is_anim))
        except Exception:
            pass
        self.load_successful = True
        self.current_image_path = path
        self.update_window_title(path)
        if os.path.exists(path):
            self.scan_directory(os.path.dirname(path))
        self.update_button_states()
        self.update_status_left()
        self.update_status_right()
        # 새 이미지 로드시 변환 상태 리셋
        self._tf_rotation = 0
        self._tf_flip_h = False
        self._tf_flip_v = False
        self._apply_transform_to_view()
        self._mark_dirty(False)
        # 새 이미지에서는 히스토리 초기화
        try:
            self._history_undo.clear()
            self._history_redo.clear()
        except Exception:
            pass
        # 탐색 성능 향상: 이웃 이미지 프리로드
        try:
            self._preload_neighbors()
        except Exception:
            pass
        # 초기 뷰 배율에 맞춰 다운샘플 적용 시도(디바운스)
        try:
            self._scale_apply_timer.start(getattr(self, "_scale_apply_delay_ms", 30))
        except Exception:
            pass
        if source in ('open', 'drop'):
            try:
                self.recent_files = update_mru(self.recent_files, path)
                parent_dir = os.path.dirname(path)
                if parent_dir and os.path.isdir(parent_dir):
                    self.last_open_dir = parent_dir
                self.save_settings()
                self.rebuild_recent_menu()
            except Exception:
                pass

        # 현재 화면 DPR에 맞춰 다운샘플 재적용 시도
        try:
            self._scale_apply_timer.start(0)
        except Exception:
            pass

    def _on_screen_changed(self, screen):
        # 새 스크린의 배율 변화도 추적하여 스케일 재적용
        try:
            if screen:
                try:
                    screen.logicalDotsPerInchChanged.connect(self._on_dpi_changed)
                except Exception:
                    pass
        except Exception:
            pass
        # 즉시 재적용(모니터 이동 직후) — DPR 전환 가드 활성화
        self._begin_dpr_transition()
        try:
            self._apply_scaled_pixmap_now()
        except Exception:
            pass

    def _on_dpi_changed(self, *args):
        # DPI 변경 디바운스: 짧은 기간 동안 중복 재적용 억제
        self._begin_dpr_transition()
        try:
            self._apply_scaled_pixmap_now()
        except Exception:
            pass

    def _begin_dpr_transition(self, guard_ms: int = 160):
        try:
            self._in_dpr_transition = True
            if self._dpr_guard_timer.isActive():
                self._dpr_guard_timer.stop()
            self._dpr_guard_timer.start(int(max(60, guard_ms)))
        except Exception:
            self._in_dpr_transition = True

    def _ensure_screen_signal_connected(self):
        if getattr(self, "_screen_signal_connected", False):
            return
        win = None
        try:
            win = self.windowHandle() if hasattr(self, 'windowHandle') else None
        except Exception:
            win = None
        if win:
            try:
                win.screenChanged.connect(self._on_screen_changed)
                self._screen_signal_connected = True
            except Exception:
                self._screen_signal_connected = False

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self._ensure_screen_signal_connected()
        except Exception:
            pass

    def event(self, e):
        # 위젯/윈도우 레벨의 DPR 변경 이벤트를 캐치하여 일관 동작 보장
        t = e.type()
        if t == QEvent.Type.DevicePixelRatioChange:
            self._begin_dpr_transition()
            try:
                self._apply_scaled_pixmap_now()
            except Exception:
                pass
            vm = str(getattr(self.image_display_area, "_view_mode", "free") or "free")
            if vm in ("fit", "fit_width", "fit_height"):
                try:
                    self.image_display_area.apply_current_view_mode()
                except Exception:
                    pass
            return super().event(e)
        return super().event(e)

    def _preload_neighbors(self):
        """현재 인덱스를 기준으로 다음/이전 이미지를 비동기로 미리 디코드.
        ImageService 내부 QImage LRU 캐시에 저장되어, 다음 이동 시 즉시 히트 가능.
        """
        if not self.image_files_in_dir:
            return
        idx = self.current_image_index
        if not (0 <= idx < len(self.image_files_in_dir)):
            return
        paths = []
        for off in range(1, self._preload_radius + 1):
            n = idx + off
            p = idx - off
            if 0 <= n < len(self.image_files_in_dir):
                paths.append(self.image_files_in_dir[n])
            if 0 <= p < len(self.image_files_in_dir):
                paths.append(self.image_files_in_dir[p])
        if paths:
            try:
                # 다음 우선도로 힌트(큰 의미는 없지만 관례상 0보다 낮은 값)
                self.image_service.preload(paths, priority=-1)
            except Exception:
                pass

    def setup_shortcuts(self):
        """키보드 단축키 설정"""
        setup_shortcuts_ext(self)
        # 사용자 지정 키 매핑 적용(설정 변경 후에도 재호출 가능)
        try:
            apply_shortcuts_ext(self)
        except Exception:
            pass

    def _apply_ui_theme_and_spacing(self):
        # 간격 적용
        try:
            m = getattr(self, "_ui_margins", (5, 5, 5, 5))
            self.main_layout.setContentsMargins(int(m[0]), int(m[1]), int(m[2]), int(m[3]))
            spacing = int(getattr(self, "_ui_spacing", 6))
            self.main_layout.setSpacing(spacing)
        except Exception:
            pass
        # 테마 적용
        theme = getattr(self, "_theme", 'dark')
        # 시스템 테마 추출 (가능한 경우), 기본은 다크
        resolved = theme
        if theme == 'system':
            try:
                import sys as _sys
                # Windows: 레지스트리 AppsUseLightTheme (0=dark, 1=light)
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
                    # 기타 OS: 현재 앱 팔레트의 윈도우 배경 밝기로 추정
                    from PyQt6.QtWidgets import QApplication  # type: ignore[import]
                    pal = QApplication.instance().palette() if QApplication.instance() else None
                    if pal:
                        c = pal.window().color()
                        # ITU-R BT.601 luma approximation
                        luma = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
                        resolved = 'light' if luma >= 127 else 'dark'
                    else:
                        resolved = 'dark'
            except Exception:
                resolved = 'dark'
        try:
            self._resolved_theme = resolved
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
            self.centralWidget().setStyleSheet(f"background-color: {bg};")
        except Exception:
            pass
        try:
            # 버튼 색/배경 모두 테마에 맞게 갱신
            button_style = f"color: {fg}; background-color: transparent;"
            for btn in [
                self.open_button,
                self.recent_button,
                self.fullscreen_button,
                self.prev_button,
                self.next_button,
                self.zoom_out_button,
                self.fit_button,
                self.zoom_in_button,
                self.rotate_left_button,
                self.rotate_right_button,
                self.settings_button,
            ]:
                btn.setStyleSheet(button_style)
        except Exception:
            pass
        try:
            self.statusBar().setStyleSheet(
                f"QStatusBar {{ background-color: {bar_bg}; border-top: 1px solid {bar_bg}; color: {fg}; }} "
                f"QStatusBar QLabel {{ color: {fg}; }} "
                "QStatusBar::item { border: 0px; }"
            )
            self.status_left_label.setStyleSheet(f"color: {fg};")
            self.status_right_label.setStyleSheet(f"color: {fg};")
        except Exception:
            pass
        try:
            # ImageView 배경도 테마에 맞추어 조정 (system 포함하여 resolved 사용)
            from PyQt6.QtGui import QColor, QBrush  # type: ignore[import]
            if resolved == 'light':
                self.image_display_area.setBackgroundBrush(QBrush(QColor("#F0F0F0")))
            else:
                self.image_display_area.setBackgroundBrush(QBrush(QColor("#373737")))
        except Exception:
            pass
        try:
            # 버튼 바 스타일도 테마 색상에 맞추어 갱신
            self.button_bar.setStyleSheet(f"background-color: transparent; QPushButton {{ color: {fg}; }}")
        except Exception:
            pass

    def toggle_fullscreen(self):
        """전체화면 모드 토글"""
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        """전체화면 모드 진입 (애니메이션 없이)"""
        fs_enter_fullscreen(self)

    def exit_fullscreen(self):
        """전체화면 모드 종료 (제목표시줄 보장)"""
        fs_exit_fullscreen(self)

    def handle_escape(self):
        """Esc 키 처리 - 전체화면 종료 또는 프로그램 종료"""
        if self.is_slideshow_active:
            self.stop_slideshow()
        elif self.is_fullscreen:
            self.exit_fullscreen()
        else:
            # 전체화면이 아닐 때는 프로그램 종료
            QApplication.quit()

    def stop_slideshow(self):
        """슬라이드쇼 종료 (향후 구현을 위한 placeholder)"""
        self.is_slideshow_active = False
        # 슬라이드쇼 타이머가 있다면 여기서 정지
        pass

    def delete_current_image(self):
        """현재 이미지를 휴지통으로 삭제 (Windows 10+ 최적화)"""
        if not self.current_image_path or not os.path.exists(self.current_image_path):
            return

        # 삭제 확인 다이얼로그
        reply = QMessageBox.question(
            self, 
            "파일 삭제", 
            f"'{os.path.basename(self.current_image_path)}'을(를) 휴지통으로 이동하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 1) 파일 잠금 방지: 애니메이션/뷰 리소스 해제
                try:
                    # QMovie 정지 및 연결 해제
                    if getattr(self, "_movie", None):
                        try:
                            try:
                                self._movie.frameChanged.disconnect(self._on_movie_frame)
                            except Exception:
                                pass
                            self._movie.stop()
                        except Exception:
                            pass
                        try:
                            self._movie.deleteLater()
                        except Exception:
                            pass
                        self._movie = None
                    # 수동 타이머 정지
                    try:
                        if getattr(self, "_anim_timer", None):
                            self._anim_timer.stop()
                    except Exception:
                        pass
                    self._anim_is_playing = False
                    try:
                        # 뷰로부터 현재 픽스맵 참조 해제 (파일 핸들은 없지만 메모리 해제 가속)
                        self.image_display_area.updatePixmapFrame(None)
                    except Exception:
                        pass
                    try:
                        # 완전 해제(장면 초기화)
                        self.image_display_area.setPixmap(None)
                    except Exception:
                        pass
                    try:
                        # 이미지 캐시 무효화
                        self.image_service.invalidate_path(self.current_image_path)
                    except Exception:
                        pass
                    try:
                        import gc
                        gc.collect()
                    except Exception:
                        pass
                except Exception:
                    pass

                # Windows 10+ 환경에 최적화된 휴지통 삭제
                move_to_trash_windows(self.current_image_path)
                
                # 현재 이미지를 목록에서 제거하고, 바로 이전 이미지로 이동
                original_index = self.current_image_index
                try:
                    if self.current_image_path in self.image_files_in_dir:
                        self.image_files_in_dir.remove(self.current_image_path)
                except Exception:
                    pass

                if self.image_files_in_dir:
                    # 이전 이미지 우선 로드
                    target_index = original_index - 1 if (isinstance(original_index, int) and original_index > 0) else 0
                    target_index = max(0, min(target_index, len(self.image_files_in_dir) - 1))
                    self.current_image_index = target_index
                    self.load_image(self.image_files_in_dir[self.current_image_index], source='nav')
                else:
                    # 모든 이미지가 삭제되면 화면 클리어
                    self.clear_display()
                
                self.update_button_states()
                # 파일 시스템 변경사항 반영을 위해 폴더 재스캔
                try:
                    self._rescan_current_dir()
                except Exception:
                    pass
                # 삭제 성공: 상태바 메시지로 안내
                try:
                    self.statusBar().showMessage("삭제됨 — 실행 취소는 휴지통에서 가능", 3000)
                except Exception:
                    pass
                
            except Exception as e:
                try:
                    QMessageBox.critical(
                        self,
                        "삭제 오류",
                        f"파일을 삭제할 수 없습니다:\n{str(e)}"
                    )
                except Exception:
                    pass

    # 삭제 기능은 delete_utils로 분리됨
    def _undo_last_delete(self):
        # 휴지통 복원은 OS/라이브러리 의존성이 높아 표준화가 어려움.
        # 우선 휴지통을 열어 사용자가 즉시 복원할 수 있게 안내.
        try:
            import subprocess, sys
            if sys.platform == "win32":
                subprocess.Popen(["explorer.exe", "shell:RecycleBinFolder"])  # 휴지통 열기
        except Exception:
            pass
        # 잠시 후 디렉터리 재스캔 시도(복원 반영)
        try:
            QTimer.singleShot(1200, getattr(self, "_rescan_current_dir", lambda: None))
        except Exception:
            try:
                self._rescan_current_dir()
            except Exception:
                pass

    def clear_display(self):
        """이미지 표시 영역 클리어"""
        self.image_display_area.setPixmap(None)
        self.current_image_path = None
        self.current_image_index = -1
        self.update_window_title()  # 제목도 초기화
        self.update_status_left()
        self.update_status_right()

    def open_file(self):
        file_path = open_file_dialog_util(self, getattr(self, "last_open_dir", ""))
        if file_path:
            try:
                self.log.info("open_dialog_selected | file=%s", os.path.basename(file_path))
            except Exception:
                pass
            success = self.load_image(file_path, source='open')
            if success:
                try:
                    parent_dir = os.path.dirname(file_path)
                    if parent_dir and os.path.isdir(parent_dir):
                        self.last_open_dir = parent_dir
                        self.save_settings()
                        try:
                            self.log.info("open_dialog_applied_last_dir | dir=%s", os.path.basename(parent_dir))
                        except Exception:
                            pass
                except Exception:
                    pass

    def load_image(self, file_path, source='other'):
        # Dirty 체크 후 정책 실행
        if self._is_dirty and self.current_image_path and os.path.normcase(file_path) != os.path.normcase(self.current_image_path):
            if not self._handle_dirty_before_action():
                try:
                    self.log.info("load_image_aborted_dirty | new=%s | cur=%s", os.path.basename(file_path), os.path.basename(self.current_image_path or ""))
                except Exception:
                    pass
                return False
        try:
            self.log.info("load_image_start | src=%s | source=%s", os.path.basename(file_path), source)
        except Exception:
            pass
        # 동기 로딩 경로
        path, img, success, _ = self.image_service.load(file_path)
        if success and img is not None:
            self._apply_loaded_image(path, img, source)
            try:
                self.log.info("load_image_ok | file=%s | w=%d | h=%d", os.path.basename(path), int(img.width()), int(img.height()))
            except Exception:
                pass
            return True
        # 실패 처리
        try:
            self.log.error("load_image_fail | file=%s", os.path.basename(file_path))
        except Exception:
            pass
        self.load_successful = False
        self.current_image_path = None
        self.image_files_in_dir = []
        self.current_image_index = -1
        self.update_window_title()
        self.update_button_states()
        self.update_status_left()
        self.update_status_right()
        return False

    # ----- 저장 흐름 -----
    def save_current_image(self) -> bool:
        if not self.load_successful or not self.current_image_path:
            return False
        # 변환이 없으면 저장 불필요
        if self._tf_rotation == 0 and not self._tf_flip_h and not self._tf_flip_v:
            return True
        try:
            # 항상 풀해상도 QImage를 사용하여 품질 보존
            img = getattr(self, "_fullres_image", None)
            if img is None or img.isNull():
                # 폴백: 뷰의 현재 픽스맵(가능하면 회피)
                pix = self.image_display_area.originalPixmap()
                if not pix or pix.isNull():
                    return False
                img = pix.toImage()
            # 진행 UI 표시
            try:
                if self._progress:
                    self._progress.setVisible(True)
                    self._progress.setValue(0)
                if self._cancel_btn:
                    self._cancel_btn.setVisible(True)
            except Exception:
                pass

            def on_progress(p: int):
                try:
                    if self._progress:
                        self._progress.setValue(max(0, min(100, int(p))))
                except Exception:
                    pass

            def on_done(ok: bool, err: str):
                try:
                    if self._progress:
                        self._progress.setVisible(False)
                    if self._cancel_btn:
                        self._cancel_btn.setVisible(False)
                except Exception:
                    pass
                if ok:
                    # 저장 후 재로드 및 상태 리셋
                    self.load_image(self.current_image_path, source='save')
                    self._mark_dirty(False)
                    try:
                        self.statusBar().showMessage("저장됨", 1800)
                    except Exception:
                        pass
                else:
                    try:
                        QMessageBox.critical(self, "저장 오류", err or "파일 저장에 실패했습니다.")
                    except Exception:
                        pass

            # 비동기 저장 실행
            self.image_service.save_async(
                img,
                self.current_image_path,
                self.current_image_path,
                self._tf_rotation,
                self._tf_flip_h,
                self._tf_flip_v,
                quality=self._jpeg_quality,
                on_progress=on_progress,
                on_done=on_done,
            )
            return True
        except Exception as e:
            try:
                QMessageBox.critical(self, "저장 오류", str(e))
            except Exception:
                pass
            return False

    def save_current_image_as(self) -> bool:
        if not self.load_successful or not self.current_image_path:
            return False
        try:
            from PyQt6.QtWidgets import QFileDialog  # type: ignore[import]
            start_dir = os.path.dirname(self.current_image_path) if self.current_image_path else ""
            dest_path, _ = QFileDialog.getSaveFileName(self, "다른 이름으로 저장", start_dir)
            if not dest_path:
                return False
            img = getattr(self, "_fullres_image", None)
            if img is None or img.isNull():
                pix = self.image_display_area.originalPixmap()
                if not pix or pix.isNull():
                    return False
                img = pix.toImage()
            ok, err = self.image_service.save_with_transform(
                img,
                self.current_image_path,
                dest_path,
                self._tf_rotation,
                self._tf_flip_h,
                self._tf_flip_v,
                quality=self._jpeg_quality,
            )
            if not ok:
                QMessageBox.critical(self, "저장 오류", err or "파일 저장에 실패했습니다.")
                return False
            # 저장 후 새 경로 로드 및 상태 리셋
            self.load_image(dest_path, source='saveas')
            self._mark_dirty(False)
            return True
        except Exception as e:
            QMessageBox.critical(self, "저장 오류", str(e))
            return False

    # ----- 스케일별 다운샘플 적용 -----
    def _apply_scaled_pixmap_now(self):
        if not self.load_successful or not self.current_image_path:
            return
        # 앵커 보존: DPR 변경/재적용 중에도 현재 보던 지점을 유지
        item_anchor_point = None
        try:
            view = self.image_display_area
            pix_item = getattr(view, "_pix_item", None)
            if pix_item:
                vp_center = view.viewport().rect().center()
                scene_center = view.mapToScene(vp_center)
                item_anchor_point = pix_item.mapFromScene(scene_center)
        except Exception:
            item_anchor_point = None
        # 애니메이션 파일은 프레임 교체 성능/동기화 문제를 피하기 위해 제외
        try:
            if self._is_current_file_animation():
                return
            if getattr(self, "_movie", None):
                return
        except Exception:
            pass
        try:
            cur_scale = float(getattr(self, "_last_scale", 1.0) or 1.0)
        except Exception:
            cur_scale = 1.0
        # DPR 추정
        try:
            dpr = float(self.image_display_area.viewport().devicePixelRatioF())
        except Exception:
            try:
                dpr = float(self.devicePixelRatioF())
            except Exception:
                dpr = 1.0
        prev_dpr = float(getattr(self, "_last_dpr", dpr) or dpr)
        dpr_changed = bool(abs(dpr - prev_dpr) > 1e-3)
        view_mode = str(getattr(self.image_display_area, "_view_mode", "free") or "free")

        # DPR 변경 + 화면 맞춤 계열: 즉시 풀해상도로 재맞춤(가장 예측 가능한 UX)
        if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
            try:
                if getattr(self, "_fullres_image", None) is not None and not self._fullres_image.isNull():
                    pm = QPixmap.fromImage(self._fullres_image)
                    self.image_display_area.updatePixmapFrame(pm)
                    self.image_display_area.set_source_scale(1.0)
                    # 다시 맞춤 수행
                    self.image_display_area.apply_current_view_mode()
                    # 앵커 복원(가능하면)
                    try:
                        if item_anchor_point is not None and getattr(self.image_display_area, "_pix_item", None):
                            new_scene_point = self.image_display_area._pix_item.mapToScene(item_anchor_point)
                            self.image_display_area.centerOn(new_scene_point)
                    except Exception:
                        pass
                    self._last_dpr = dpr
                    return
            except Exception:
                pass
        # 스케일 >= 1: 풀해상도로 복귀
        if cur_scale >= 1.0:
            try:
                if getattr(self, "_fullres_image", None) is not None and not self._fullres_image.isNull():
                    pm = QPixmap.fromImage(self._fullres_image)
                    self.image_display_area.updatePixmapFrame(pm)
                    self.image_display_area.set_source_scale(1.0)
            except Exception:
                pass
            # DPR 변경 시, 화면 맞춤 계열이면 다시 맞춤 수행
            if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
                try:
                    self.image_display_area.apply_current_view_mode()
                except Exception:
                    pass
            # 화면 맞춤 재수행(필요 시)
            if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
                try:
                    self.image_display_area.apply_current_view_mode()
                except Exception:
                    pass
            # 앵커 복원(가능한 경우)
            try:
                if item_anchor_point is not None and getattr(self.image_display_area, "_pix_item", None):
                    new_scene_point = self.image_display_area._pix_item.mapToScene(item_anchor_point)
                    self.image_display_area.centerOn(new_scene_point)
            except Exception:
                pass
            self._last_dpr = dpr
            # DPR 전환 중에는 추가 스케일 디바운스 억제
            if getattr(self, "_in_dpr_transition", False):
                return
            return
        # 사용자 정책: 100% 미만에서도 썸네일 대신 항상 원본 사용
        if getattr(self, "_disable_scaled_cache_below_100", False) and cur_scale < 1.0:
            try:
                if getattr(self, "_fullres_image", None) is not None and not self._fullres_image.isNull():
                    pm = QPixmap.fromImage(self._fullres_image)
                    self.image_display_area.updatePixmapFrame(pm)
                    self.image_display_area.set_source_scale(1.0)
            except Exception:
                pass
            # DPR 변경 시 화면 맞춤 계열이면 재맞춤
            if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
                try:
                    self.image_display_area.apply_current_view_mode()
                except Exception:
                    pass
            # 앵커 복원
            try:
                if item_anchor_point is not None and getattr(self.image_display_area, "_pix_item", None):
                    new_scene_point = self.image_display_area._pix_item.mapToScene(item_anchor_point)
                    self.image_display_area.centerOn(new_scene_point)
            except Exception:
                pass
            self._last_dpr = dpr
            return
        # 다운샘플 요청
        try:
            scaled = self.image_service.get_scaled_image(self.current_image_path, cur_scale, dpr)
        except Exception:
            scaled = None
        if scaled is None or scaled.isNull():
            # 폴백: 풀해상도 유지
            try:
                if getattr(self, "_fullres_image", None) is not None and not self._fullres_image.isNull():
                    pm_fb = QPixmap.fromImage(self._fullres_image)
                    self.image_display_area.updatePixmapFrame(pm_fb)
                    self.image_display_area.set_source_scale(1.0)
            except Exception:
                pass
            # DPR 변경 시 화면 맞춤 계열이면 재맞춤
            if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
                try:
                    self.image_display_area.apply_current_view_mode()
                except Exception:
                    pass
            # 앵커 복원
            try:
                if item_anchor_point is not None and getattr(self.image_display_area, "_pix_item", None):
                    new_scene_point = self.image_display_area._pix_item.mapToScene(item_anchor_point)
                    self.image_display_area.centerOn(new_scene_point)
            except Exception:
                pass
            self._last_dpr = dpr
            if getattr(self, "_in_dpr_transition", False):
                return
            return
        # 소스 스케일 추정: scaled는 base*(qscale*dpr)로 생성됨. 비율을 역으로 환산
        try:
            base_w = int(self._fullres_image.width()) if getattr(self, "_fullres_image", None) else 0
            base_h = int(self._fullres_image.height()) if getattr(self, "_fullres_image", None) else 0
            sw = int(scaled.width())
            sh = int(scaled.height())
            s_w = (sw / float(base_w)) / float(dpr) if base_w > 0 else cur_scale
            s_h = (sh / float(base_h)) / float(dpr) if base_h > 0 else cur_scale
            src_scale = max(0.01, min(1.0, min(s_w, s_h)))
        except Exception:
            src_scale = max(0.01, min(1.0, cur_scale))
        # 픽스맵 교체 및 소스 스케일 보정
        try:
            pm_scaled = QPixmap.fromImage(scaled)
            self.image_display_area.updatePixmapFrame(pm_scaled)
            self.image_display_area.set_source_scale(src_scale)
            # 자연 크기는 이미 _apply_loaded_image에서 설정됨. 없을 경우 보완
            if not getattr(self.image_display_area, "_natural_width", 0):
                try:
                    if getattr(self, "_fullres_image", None):
                        self.image_display_area._natural_width = int(self._fullres_image.width())
                        self.image_display_area._natural_height = int(self._fullres_image.height())
                except Exception:
                    pass
        except Exception:
            pass
        # DPR 변경 시 화면 맞춤 계열이면 재맞춤
        if dpr_changed and view_mode in ("fit", "fit_width", "fit_height"):
            try:
                self.image_display_area.apply_current_view_mode()
            except Exception:
                pass
        # 자유 줌이며 시각적 크기 보존 옵션이 켜져 있으면 배율 보정(prev_dpr/dpr)
        elif dpr_changed and getattr(self, "_preserve_visual_size_on_dpr_change", False):
            try:
                last_scale = float(getattr(self, "_last_scale", 1.0) or 1.0)
                desired_scale = last_scale * (prev_dpr / dpr)
                self.image_display_area.set_absolute_scale(desired_scale)
            except Exception:
                pass
        # 앵커 복원
        try:
            if item_anchor_point is not None and getattr(self.image_display_area, "_pix_item", None):
                new_scene_point = self.image_display_area._pix_item.mapToScene(item_anchor_point)
                self.image_display_area.centerOn(new_scene_point)
        except Exception:
            pass
        self._last_dpr = dpr
        if getattr(self, "_in_dpr_transition", False):
            return
        # 다운샘플 표시 직후, 1회성 원본 업그레이드를 예약(줌 크기와 무관)
        try:
            if getattr(self, "_fullres_image", None) is not None and not self._fullres_image.isNull():
                # 애니메이션이 아니고 현재 소스 스케일이 1.0 미만일 때만 의미 있음
                ss = float(getattr(self.image_display_area, "_source_scale", 1.0) or 1.0)
                if ss < 1.0:
                    if self._fullres_upgrade_timer.isActive():
                        self._fullres_upgrade_timer.stop()
                    # 짧은 지연 후 업그레이드(연속 줌 중에는 마지막 상태에 수렴)
                    self._fullres_upgrade_timer.start(120)
        except Exception:
            pass

    def _upgrade_to_fullres_if_needed(self):
        # 현재 표시를 원본 QImage로 한번만 업그레이드(시각 배율 불변)
        try:
            if not self.load_successful or not self.current_image_path:
                return
            # 애니메이션 파일은 제외
            if self._is_current_file_animation() or getattr(self, "_movie", None):
                return
            if getattr(self, "_fullres_image", None) is None or self._fullres_image.isNull():
                return
            # 이미 원본이면 불필요
            ss = float(getattr(self.image_display_area, "_source_scale", 1.0) or 1.0)
            if ss >= 1.0:
                return
            # 앵커 보존
            item_anchor_point = None
            try:
                view = self.image_display_area
                pix_item = getattr(view, "_pix_item", None)
                if pix_item:
                    vp_center = view.viewport().rect().center()
                    scene_center = view.mapToScene(vp_center)
                    item_anchor_point = pix_item.mapFromScene(scene_center)
            except Exception:
                item_anchor_point = None
            # DPR 추출
            try:
                dpr = float(self.image_display_area.viewport().devicePixelRatioF())
            except Exception:
                try:
                    dpr = float(self.devicePixelRatioF())
                except Exception:
                    dpr = 1.0
            pm = QPixmap.fromImage(self._fullres_image)
            self.image_display_area.updatePixmapFrame(pm)
            self.image_display_area.set_source_scale(1.0)
            # 앵커 복원
            try:
                if item_anchor_point is not None and getattr(self.image_display_area, "_pix_item", None):
                    new_scene_point = self.image_display_area._pix_item.mapToScene(item_anchor_point)
                    self.image_display_area.centerOn(new_scene_point)
            except Exception:
                pass
        except Exception:
            pass

    def _handle_dirty_before_action(self) -> bool:
        # 정책 적용
        policy = getattr(self, "_save_policy", 'discard')
        if policy == 'discard':
            return True
        if policy == 'overwrite':
            return self.save_current_image()
        if policy == 'save_as':
            return self.save_current_image_as()
        # ask
        box = QMessageBox(self)
        box.setWindowTitle("변경 내용 저장")
        box.setText("회전/뒤집기 변경 내용을 저장하시겠습니까?")
        btn_save = box.addButton("저장", QMessageBox.ButtonRole.AcceptRole)
        btn_save_as = box.addButton("다른 이름으로", QMessageBox.ButtonRole.ActionRole)
        btn_discard = box.addButton("무시", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = box.addButton("취소", QMessageBox.ButtonRole.RejectRole)
        box.setIcon(QMessageBox.Icon.Question)
        box.exec()
        clicked = box.clickedButton()
        if clicked == btn_save:
            return self.save_current_image()
        if clicked == btn_save_as:
            return self.save_current_image_as()
        if clicked == btn_discard:
            # 변경 사항 폐기
            return True
        return False

    # ----- 설정 다이얼로그 -----
    def open_settings_dialog(self):
        # 이미 열린 설정창이 있으면 활성화만
        if hasattr(self, "_settings_dialog") and self._settings_dialog and self._settings_dialog.isVisible():
            try:
                self._settings_dialog.raise_()
                self._settings_dialog.activateWindow()
                # 요청에 따라 단축키 탭 초점 이동도 지원
                try:
                    self._settings_dialog.focus_shortcuts_tab()
                except Exception:
                    pass
                return
            except Exception:
                pass
        # 대화상자 열릴 때 단축키 비활성
        self._set_global_shortcuts_enabled(False)
        dlg = SettingsDialog(self)
        self._settings_dialog = dlg
        dlg.load_from_viewer(self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            dlg.apply_to_viewer(self)
            # 즉시 UI 반영 및 저장
            try:
                self._apply_ui_theme_and_spacing()
            except Exception:
                pass
            # 기본 보기 모드는 업데이트하되, 현재 보기(줌/위치)는 변경하지 않음
            self._preferred_view_mode = getattr(self, "_default_view_mode", 'fit')
            # 단축키 설정 변경 가능성 반영
            try:
                apply_shortcuts_ext(self)
            except Exception:
                pass
            self.save_settings()
        try:
            self._settings_dialog = None
        except Exception:
            pass
        # 대화상자 닫힐 때 단축키 복원
        self._set_global_shortcuts_enabled(True)

    def open_shortcuts_help(self):
        # 대화상자 열릴 때 단축키 비활성
        self._set_global_shortcuts_enabled(False)
        dlg = ShortcutsHelpDialog(self)
        dlg.exec()
        # 닫힌 후 복원
        self._set_global_shortcuts_enabled(True)

    def scan_directory(self, dir_path):
        try:
            self.log.info("scan_dir_start | dir=%s", os.path.basename(dir_path or ""))
        except Exception:
            pass
        self.image_files_in_dir, self.current_image_index = self.image_service.scan_directory(dir_path, self.current_image_path)
        # 폴더만 열어 현재 선택된 파일이 없을 때 첫 이미지로 기본 설정
        try:
            if (self.current_image_index is None or self.current_image_index < 0) and self.image_files_in_dir:
                self.current_image_index = 0
        except Exception:
            if self.image_files_in_dir:
                self.current_image_index = 0
        self.update_button_states()
        self.update_status_left()
        try:
            self.log.info("scan_dir_done | dir=%s | count=%d | cur=%d", os.path.basename(dir_path or ""), len(self.image_files_in_dir), int(self.current_image_index))
        except Exception:
            pass

    def _rescan_current_dir(self):
        """현재 폴더를 재스캔하여 파일 목록을 최신화한다."""
        try:
            dir_path = None
            if self.current_image_path:
                d = os.path.dirname(self.current_image_path)
                if d and os.path.isdir(d):
                    dir_path = d
            if not dir_path and getattr(self, "last_open_dir", "") and os.path.isdir(self.last_open_dir):
                dir_path = self.last_open_dir
            if dir_path:
                self.scan_directory(dir_path)
        except Exception:
            pass

    def show_prev_image(self):
        nav_show_prev_image(self)

    def show_next_image(self):
        nav_show_next_image(self)

    def load_image_at_current_index(self):
        nav_load_image_at_current_index(self)

    def update_button_states(self):
        nav_update_button_states(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # ImageView가 자체 맞춤을 처리
        pass

    def reset_to_100(self):
        if not self.load_successful:
            return
        self.fit_mode = False
        self.scale_factor = 1.0
        # ImageView에 100% 적용
        self.image_display_area.reset_to_100()
        self.update_button_states()
        self.update_status_right()

    # QGraphicsView 기반을 사용하므로 별도 이벤트 필터 불필요
    def eventFilter(self, obj, event):
        # 세부 DnD 처리는 DnDEventFilter에서 담당
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        try:
            self.log.info("window_close")
        except Exception:
            pass
        try:
            self.save_last_session()
        except Exception:
            pass
        super().closeEvent(event)
        super().closeEvent(event)