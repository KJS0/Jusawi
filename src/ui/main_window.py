import os
import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QApplication, QMainWindow, QLabel, QSizePolicy, QMenu, QTextEdit  # type: ignore[import]
from PyQt6.QtCore import QTimer, Qt, QSettings, QPointF, QEvent, QUrl, pyqtSignal, QObject  # type: ignore[import]
from PyQt6.QtGui import QKeySequence, QShortcut, QImage, QAction, QPixmap, QMovie, QColorSpace, QDesktopServices  # type: ignore[import]

from .image_view import ImageView
from .filmstrip import FilmstripView
from . import commands as viewer_cmd
from . import animation_controller as anim
from .state import TransformState, ViewerState
from . import display_scaling as ds
from .dirty_guard import handle_dirty_before_action as dg_handle
from .dir_utils import rescan_current_dir as dir_rescan
from . import dir_scan as dir_scan_ext
from .theme import apply_ui_theme_and_spacing as apply_theme
from . import file_commands as file_cmd
from . import image_loader as img_loader
from . import history as hist
from ..utils.file_utils import open_file_dialog_util, cleanup_leftover_temp_and_backup
from ..utils.delete_utils import move_to_trash_windows
from ..storage.mru_store import normalize_path, update_mru
from .z_dnd_bridge import handle_dropped_files as dnd_handle_files
from .z_dnd_bridge import handle_dropped_folders as dnd_handle_folders
from .z_dnd_bridge import drag_enter as dnd_drag_enter, drag_move as dnd_drag_move, drop as dnd_drop
from .fullscreen_controller import enter_fullscreen as fs_enter_fullscreen, exit_fullscreen as fs_exit_fullscreen
from .menu_builder import rebuild_recent_menu as build_recent_menu
from .menu_builder import rebuild_log_menu as build_log_menu
from ..shortcuts.shortcuts_manager import apply_shortcuts as apply_shortcuts_ext
from ..dnd.event_filters import DnDEventFilter
from ..services.session_service import save_last_session as save_session_ext, restore_last_session as restore_session_ext
from ..storage.settings_store import load_settings as load_settings_ext, save_settings as save_settings_ext
from ..utils.navigation import NavigationController, show_prev_image as nav_show_prev_image, show_next_image as nav_show_next_image, load_image_at_current_index as nav_load_image_at_current_index, update_button_states as nav_update_button_states
from .title_status import update_window_title as ts_update_window_title, update_status_left as ts_update_status_left, update_status_right as ts_update_status_right
from . import info_panel
from .layout_builder import build_top_and_status_bars
from .shortcuts_utils import set_global_shortcuts_enabled
from .view_utils import clear_display as view_clear_display
from .utils_misc import clamp as util_clamp, enable_dnd_on as util_enable_dnd_on, setup_global_dnd as util_setup_global_dnd, handle_escape as util_handle_escape
from . import lifecycle
from . import log_actions
from ..dnd.dnd_setup import setup_global_dnd as setup_global_dnd_ext, enable_dnd as enable_dnd_ext
from ..services.image_service import ImageService
from . import dialogs as dlg
from ..utils.logging_setup import get_logger, get_log_dir, export_logs_zip, suggest_logs_zip_name, open_logs_folder
from ..services.ratings_store import get_image as ratings_get_image, upsert_image as ratings_upsert_image  # type: ignore
from . import rating_bar
from . import transform_ui
from . import map_click

class JusawiViewer(QMainWindow):
    def __init__(self, skip_session_restore: bool = False):
        super().__init__()
        # 세션 복원 스킵 여부(명령줄로 파일/폴더가 지정된 경우 사용)
        self._skip_session_restore = bool(skip_session_restore)
        self.setWindowTitle("Jusawi")
        self.log = get_logger("ui.JusawiViewer")
        # 창 기본 초기화 크기/위치 정책: 복원 비활성화, 기본 크기 지정
        self._restore_window_geometry = False
        try:
            self.resize(1280, 800)
            self.move(80, 60)
        except Exception:
            pass

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
        # 배경/스타일은 theme.apply_ui_theme_and_spacing에서 일괄 적용
        central_widget.setStyleSheet("")
        # Drag & Drop 허용 (초기 상태 포함 창 어디서나 동작하도록 중앙/뷰포트에도 적용)
        self.setAcceptDrops(True)
        central_widget.setAcceptDrops(True)
        central_widget.installEventFilter(self)
        # DnD 이벤트 필터 설치(윈도우/중앙/뷰포트에서 일관 처리)
        try:
            self._dnd_filter = DnDEventFilter(self)
            central_widget.installEventFilter(self._dnd_filter)
        except Exception:
            pass

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
            try:
                self.image_display_area.viewport().installEventFilter(self._dnd_filter)
            except Exception:
                pass
        except Exception:
            pass
        self.image_display_area.installEventFilter(self)
        try:
            self.image_display_area.installEventFilter(self._dnd_filter)
        except Exception:
            pass
        # 메인 콘텐츠 영역: 이미지 + 정보 패널(우측) → QSplitter로 가변 너비
        from PyQt6.QtWidgets import QSplitter  # type: ignore[import]
        self.content_widget = QWidget(central_widget)
        self.content_layout = QHBoxLayout(self.content_widget)
        try:
            self.content_layout.setContentsMargins(0, 0, 0, 0)
            self.content_layout.setSpacing(6)
        except Exception:
            pass
        # 스플리터 제거 후, 이미지 영역은 스프링으로 확장
        self.content_layout.addWidget(self.image_display_area, 1)
        # 정보 패널 (텍스트 + 지도 미리보기) → 내부도 QSplitter로 가변 높이
        self.info_panel = QWidget(self.content_widget)
        self.info_panel_layout = QVBoxLayout(self.info_panel)
        try:
            self.info_panel_layout.setContentsMargins(0, 0, 0, 0)
            self.info_panel_layout.setSpacing(6)
        except Exception:
            pass
        self.info_text = QTextEdit(self.info_panel)
        try:
            self.info_text.setReadOnly(True)
            self.info_text.setMinimumWidth(280)
        except Exception:
            pass
        self.info_map_label = QLabel(self.info_panel)
        try:
            self.info_map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.info_map_label.setText("여기에 지도가 표시됩니다.")
            try:
                self.info_text.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            except Exception:
                pass
        except Exception:
            pass
        # 스플리터 롤백: 직접 위젯 배치
        self.info_panel_layout.addWidget(self.info_text)
        self.info_panel_layout.addWidget(self.info_map_label)
        self.info_panel.setVisible(False)
        self.content_layout.addWidget(self.info_panel)
        # 수평 레이아웃으로 이미지/정보 패널 표시
        self.main_layout.addWidget(self.content_widget, 1)

        # 하단 필름 스트립
        self.filmstrip = FilmstripView(self)
        try:
            self.filmstrip.currentIndexChanged.connect(self._on_filmstrip_index_changed)
        except Exception:
            pass
        # 하단 필름 스트립을 고정 배치로 롤백
        self.main_layout.addWidget(self.filmstrip, 0)

        # 필름 스트립 컨트롤 바(별점/플래그)
        try:
            rating_bar.create(self)
        except Exception:
            pass

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
        # 100% 이하 배율에서도 스케일 디코딩/캐시를 적극 활용하여 대용량 표시 성능 개선
        self._disable_scaled_cache_below_100 = False
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
        # 현재 픽스맵이 스케일 프리뷰인지 여부(원본 업그레이드 필요 판단용)
        self._is_scaled_preview = False
        # 직전 프레임이 원본으로 업그레이드 된 직후인지(스케일 적용 전 깜빡임 방지)
        self._just_upgraded_fullres = False
        # 프리로드 설정(다음/이전 1장씩)
        self._preload_radius = 1

        # 자연어 검색/임베딩 관련 기능 제거됨

        build_top_and_status_bars(self)

        # 회전 버튼은 위에서 생성됨

        self.update_status_left()
        self.update_status_right()

        # 단축키: 별점 0..5, 플래그 Z/X/C
        try:
            rating_bar.register_shortcuts(self)
        except Exception:
            pass

        # 정보 패널/지도 관련 초기화
        info_panel.setup_info_panel(self)

        # 초기 레이아웃 사이즈 조정
        try:
            self._update_info_panel_sizes()
        except Exception:
            pass

        # 키보드 단축키 설정
        self.setup_shortcuts()
        
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
        # 내비게이션 컨트롤러
        try:
            self._nav = NavigationController(self)
        except Exception:
            self._nav = None

    def clamp(self, value, min_v, max_v):
        return util_clamp(value, min_v, max_v)

    def _enable_dnd_on(self, widget):
        util_enable_dnd_on(widget, self)

    def _setup_global_dnd(self):
        util_setup_global_dnd(self)

    def _set_global_shortcuts_enabled(self, enabled: bool) -> None:
        set_global_shortcuts_enabled(self, enabled)

    # ----- Undo/Redo 히스토리 -----
    def _capture_state(self):
        return hist.capture_state(self)

    def _restore_state(self, state) -> None:
        hist.restore_state(self, state)

    def _history_push(self) -> None:
        hist.history_push(self)

    # 전체 Viewer 상태 스냅샷/복원(옵셔널 사용 지점에서 활용)
    def snapshot_viewer_state(self) -> ViewerState:
        return ViewerState.snapshot_from(self)

    def restore_viewer_state(self, state: ViewerState) -> None:
        try:
            if not isinstance(state, ViewerState):
                return
            state.restore_into(self)
            # 경로/인덱스에 맞춰 이미지/뷰 갱신
            if 0 <= self.current_image_index < len(self.image_files_in_dir):
                self.load_image_at_current_index()
            self._apply_transform_to_view()
            self.update_button_states()
            self.update_status_right()
        except Exception:
            pass

    def undo_action(self) -> None:
        hist.undo(self)

    def redo_action(self) -> None:
        hist.redo(self)

    # Settings: 저장/로드
    def load_settings(self):
        load_settings_ext(self)

    def save_settings(self):
        save_settings_ext(self)

    # 최근 항목 유틸은 mru_store로 분리됨

    def rebuild_recent_menu(self):
        build_recent_menu(self)
        try:
            build_log_menu(self)
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
        log_actions.open_logs_folder(self)

    def _export_logs_zip(self):
        log_actions.export_logs_zip(self)

    # Drag & Drop 지원: 유틸
    def _handle_dropped_files(self, files):
        dnd_handle_files(self, files)

    def _handle_dropped_folders(self, folders):
        dnd_handle_folders(self, folders)

    # Drag & Drop 이벤트 핸들러
    def dragEnterEvent(self, event):
        dnd_drag_enter(self, event)

    def dragMoveEvent(self, event):
        dnd_drag_move(self, event)

    def dropEvent(self, event):
        dnd_drop(self, event)

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
        return anim.is_current_file_animation(self)

    def anim_prev_frame(self):
        anim.prev_frame(self)

    def anim_next_frame(self):
        anim.next_frame(self)

    def anim_toggle_play(self):
        anim.toggle_play(self)

    def _on_anim_tick(self):
        anim.on_tick(self)

    def _on_movie_frame(self, frame_index: int):
        anim.on_movie_frame(self, frame_index)

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
        viewer_cmd.fit_to_window(self)

    def fit_to_width(self):
        viewer_cmd.fit_to_width(self)

    def fit_to_height(self):
        viewer_cmd.fit_to_height(self)

    def zoom_in(self):
        viewer_cmd.zoom_in(self)

    def zoom_out(self):
        viewer_cmd.zoom_out(self)

    def on_wheel_zoom(self, delta_y, ctrl, vp_anchor):
        # ImageView가 휠 이벤트를 처리하므로 이 메서드는 사용하지 않습니다.
        pass

    def update_window_title(self, file_path=None):
        """창 제목 업데이트"""
        ts_update_window_title(self, file_path)

    # ----- 변환 상태 관리 -----
    def _apply_transform_to_view(self):
        return transform_ui.apply_transform_to_view(self)

    def _mark_dirty(self, dirty: bool = True):
        self._is_dirty = bool(dirty)
        self.update_window_title(self.current_image_path)
        self.update_status_right()

    def get_transform_status_text(self) -> str:
        return transform_ui.get_transform_status_text(self)

    def rotate_cw_90(self):
        viewer_cmd.rotate_cw_90(self)

    def rotate_ccw_90(self):
        viewer_cmd.rotate_ccw_90(self)

    def rotate_180(self):
        viewer_cmd.rotate_180(self)

    def flip_horizontal(self):
        viewer_cmd.flip_horizontal(self)

    def flip_vertical(self):
        viewer_cmd.flip_vertical(self)

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
        img_loader.apply_loaded_image(self, path, img, source)
        try:
            rating_bar.refresh(self)
        except Exception:
            pass

    def _on_screen_changed(self, screen):
        ds.on_screen_changed(self, screen)

    def _on_dpi_changed(self, *args):
        ds.on_dpi_changed(self, *args)
        try:
            self._update_info_panel_sizes()
        except Exception:
            pass

    def _begin_dpr_transition(self, guard_ms: int = 160):
        ds.begin_dpr_transition(self, guard_ms)

    def _ensure_screen_signal_connected(self):
        ds.ensure_screen_signal_connected(self)
        try:
            self._update_info_panel_sizes()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        lifecycle.on_show(self, event)
        try:
            self._update_info_panel_sizes()
        except Exception:
            pass
        try:
            # 좌우 합계 100% 강제: 스플리터 폭 기준으로 남는 픽셀까지 분배
            if getattr(self, "_content_splitter", None):
                total = max(2, int(self._content_splitter.width()))
                left = int(total * 0.58)
                right = total - left
                # 최소 폭 보장 후 초과분을 반영
                min_left, min_right = 200, 200
                if left < min_left:
                    right -= (min_left - left)
                    left = min_left
                if right < min_right:
                    left -= (min_right - right)
                    right = min_right
                left = max(1, left)
                right = max(1, total - left)
                self._content_splitter.setSizes([left, right])
        except Exception:
            pass

    def event(self, e):
        if lifecycle.before_event(self, e):
            return super().event(e)
        return super().event(e)

    def keyPressEvent(self, event):
        try:
            # 숫자 0..5: 별점 바로 적용 (충돌 단축키보다 우선 처리)
            if event.modifiers() == Qt.KeyboardModifier.NoModifier:
                k = event.key()
                if Qt.Key.Key_0 <= k <= Qt.Key.Key_5:
                    self._on_set_rating(int(k) - int(Qt.Key.Key_0))
                    event.accept()
                    return
                # 플래그: Z=pick, X=rejected, C=unflagged
                if k == Qt.Key.Key_Z:
                    self._on_set_flag('pick')
                    event.accept()
                    return
                if k == Qt.Key.Key_X:
                    self._on_set_flag('rejected')
                    event.accept()
                    return
                if k == Qt.Key.Key_C:
                    self._on_set_flag('unflagged')
                    event.accept()
                    return
        except Exception:
            pass
        super().keyPressEvent(event)

    def _preload_neighbors(self):
        img_loader.preload_neighbors(self)

    def setup_shortcuts(self):
        """키보드 단축키 설정"""
        apply_shortcuts_ext(self)

    def _apply_ui_theme_and_spacing(self):
        apply_theme(self)
        try:
            self._update_info_panel_sizes()
        except Exception:
            pass
        # filmstrip 테마 위임만 유지
        try:
            is_light = (getattr(self, "_resolved_theme", "dark") == "light")
            if hasattr(self, 'filmstrip') and self.filmstrip is not None:
                try:
                    self.filmstrip.apply_theme(is_light)
                except Exception:
                    pass
        except Exception:
            pass

    def _refresh_rating_flag_bar(self):
        return rating_bar.refresh(self)

    def _on_set_rating(self, n: int):
        return rating_bar.set_rating(self, n)

    def _on_set_flag(self, f: str):
        return rating_bar.set_flag(self, f)

    def toggle_fullscreen(self):
        """전체화면 모드 토글"""
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def mousePressEvent(self, event):
        try:
            if map_click.handle_mouse_press(self, event):
                event.accept()
                return
        except Exception:
            pass
        super().mousePressEvent(event)

    def enter_fullscreen(self):
        """전체화면 모드 진입 (애니메이션 없이)"""
        fs_enter_fullscreen(self)
        try:
            if hasattr(self, 'filmstrip') and self.filmstrip is not None:
                self.filmstrip.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, '_rating_flag_bar') and self._rating_flag_bar is not None:
                self._rating_flag_bar.setVisible(False)
        except Exception:
            pass

    def exit_fullscreen(self):
        """전체화면 모드 종료 (제목표시줄 보장)"""
        fs_exit_fullscreen(self)
        try:
            if hasattr(self, 'filmstrip') and self.filmstrip is not None:
                self.filmstrip.setVisible(True)
        except Exception:
            pass
        try:
            if hasattr(self, '_rating_flag_bar') and self._rating_flag_bar is not None:
                self._rating_flag_bar.setVisible(True)
        except Exception:
            pass

    def handle_escape(self):
        util_handle_escape(self)

    def stop_slideshow(self):
        """슬라이드쇼 종료 (향후 구현을 위한 placeholder)"""
        self.is_slideshow_active = False
        # 슬라이드쇼 타이머가 있다면 여기서 정지
        pass

    def delete_current_image(self):
        file_cmd.delete_current_image(self)

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
        view_clear_display(self)

    def open_file(self):
        file_cmd.open_file(self)

    def load_image(self, file_path, source='other'):
        return img_loader.load_image(self, file_path, source)

    # ----- 저장 흐름 -----
    def save_current_image(self) -> bool:
        return file_cmd.save_current_image(self)

    def save_current_image_as(self) -> bool:
        return file_cmd.save_current_image_as(self)

    # ----- 스케일별 다운샘플 적용 -----
    def _apply_scaled_pixmap_now(self):
        ds.apply_scaled_pixmap_now(self)

    def _upgrade_to_fullres_if_needed(self):
        ds.upgrade_to_fullres_if_needed(self)

    def _handle_dirty_before_action(self) -> bool:
        return dg_handle(self)

    # ----- 설정 다이얼로그 -----
    def open_settings_dialog(self):
        dlg.open_settings_dialog(self)

    def open_shortcuts_help(self):
        dlg.open_shortcuts_help(self)

    # EXIF 열람 기능 제거됨

    def open_ai_analysis_dialog(self):
        dlg.open_ai_analysis_dialog(self)

    def open_natural_search_dialog(self):
        dlg.open_natural_search_dialog(self)

    def open_similar_search_dialog(self):
        cur = self.current_image_path or ""
        if not cur or not os.path.isfile(cur):
            try:
                self.statusBar().showMessage("먼저 사진을 열어주세요.", 3000)
            except Exception:
                pass
            return
        folder = os.path.dirname(cur)
        try:
            from .similar_search_dialog import SimilarSearchDialog
            dlg_ = SimilarSearchDialog(self, cur, folder)
            dlg_.exec()
        except Exception:
            pass

    # ----- 정보 패널 -----
    def toggle_info_panel(self) -> None:
        return info_panel.toggle_info_panel(self)

    def _format_bytes(self, num_bytes: int) -> str:
        return info_panel.format_bytes(num_bytes)

    def _safe_frac_to_float(self, v):
        return info_panel._safe_frac_to_float(v)

    def update_info_panel(self) -> None:
        return info_panel.update_info_panel(self)

    def _dump_exif_all(self, path: str) -> str:
        from .exif_dump import dump_exif_all
        return dump_exif_all(path)

    # EXIF 탭 제거됨

    # ----- 지도 비동기 로딩 유틸 -----
    def _schedule_map_fetch(self, lat: float, lon: float, w: int, h: int, zoom: int):
        return info_panel.schedule_map_fetch(self, lat, lon, w, h, zoom)

    def _kick_map_fetch(self):
        return info_panel.kick_map_fetch(self)

    def _on_map_ready(self, token: int, pm):
        return info_panel.on_map_ready(self, token, pm)

    def _update_info_panel_sizes(self):
        return info_panel.update_info_panel_sizes(self)

    def scan_directory(self, dir_path):
        return dir_scan_ext.scan_directory(self, dir_path)

    def _rescan_current_dir(self):
        return dir_scan_ext.rescan_current_dir(self)

    def show_prev_image(self):
        if getattr(self, "_nav", None):
            self._nav.show_prev_image()
        else:
            nav_show_prev_image(self)

    def show_next_image(self):
        if getattr(self, "_nav", None):
            self._nav.show_next_image()
        else:
            nav_show_next_image(self)

    def _on_filmstrip_index_changed(self, row: int):
        try:
            if 0 <= row < len(self.image_files_in_dir):
                # 동일 인덱스면 재로딩 방지
                if int(self.current_image_index) == int(row):
                    return
                self.current_image_index = row
                self.load_image_at_current_index()
                try:
                    # 자동 스크롤(중앙 정렬)
                    self.filmstrip.set_current_index(row)
                except Exception:
                    pass
                try:
                    rating_bar.refresh(self)
                except Exception:
                    pass
        except Exception:
            pass

    def load_image_at_current_index(self):
        if getattr(self, "_nav", None):
            self._nav.load_image_at_current_index()
        else:
            nav_load_image_at_current_index(self)
        try:
            rating_bar.refresh(self)
        except Exception:
            pass

    def update_button_states(self):
        if getattr(self, "_nav", None):
            self._nav.update_button_states()
        else:
            nav_update_button_states(self)