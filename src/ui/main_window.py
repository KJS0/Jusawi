import os
import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QApplication, QMainWindow, QLabel, QSizePolicy, QMenu  # type: ignore[import]
from PyQt6.QtCore import QTimer, Qt, QSettings, QPointF  # type: ignore[import]
from PyQt6.QtGui import QKeySequence, QShortcut, QImage, QAction, QPixmap  # type: ignore[import]

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

class JusawiViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jusawi")

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

        self.button_layout = QHBoxLayout()
        self.open_button = QPushButton("열기")
        self.open_button.clicked.connect(self.open_file)
        # 최근 메뉴를 별도 버튼에 연결
        self.recent_menu = QMenu(self)
        self.recent_button = QPushButton("최근 파일")
        self.recent_button.setMenu(self.recent_menu)

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
        # 회전 버튼(확대 바로 옆)
        self.button_layout.addWidget(self.rotate_left_button)
        self.button_layout.addWidget(self.rotate_right_button)
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
        
        # 이미지 라벨에 초기 포커스 설정
        self.image_display_area.setFocus()
        
        self.update_button_states()

        # 전역 DnD 지원: 주요 위젯에 일괄 적용
        self._setup_global_dnd()

        # 전체화면 진입 전 스타일 복원용 변수
        self._stylesheet_before_fullscreen = None

        # 설정 로드 및 최근/세션 복원
        self.load_settings()
        self.rebuild_recent_menu()
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

    def clamp(self, value, min_v, max_v):
        return max(min_v, min(value, max_v))

    def _enable_dnd_on(self, widget):
        enable_dnd_ext(widget, self)

    def _setup_global_dnd(self):
        setup_global_dnd_ext(self)

    # Settings: 저장/로드
    def load_settings(self):
        load_settings_ext(self)

    def save_settings(self):
        save_settings_ext(self)

    # 최근 항목 유틸은 mru_store로 분리됨

    def rebuild_recent_menu(self):
        build_recent_menu(self)

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

    def on_cursor_pos_changed(self, x: int, y: int):
        self._last_cursor_x = x
        self._last_cursor_y = y
        self.update_status_right()

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
        self._tf_rotation = (self._tf_rotation + 90) % 360
        self._apply_transform_to_view()
        self._mark_dirty(True)
        # 화면 맞춤 모드일 경우 재-맞춤
        if getattr(self.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
            self.image_display_area.apply_current_view_mode()

    def rotate_ccw_90(self):
        if not self.load_successful:
            return
        self._tf_rotation = (self._tf_rotation - 90) % 360
        self._apply_transform_to_view()
        self._mark_dirty(True)
        if getattr(self.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
            self.image_display_area.apply_current_view_mode()

    def rotate_180(self):
        if not self.load_successful:
            return
        self._tf_rotation = (self._tf_rotation + 180) % 360
        self._apply_transform_to_view()
        self._mark_dirty(True)
        if getattr(self.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
            self.image_display_area.apply_current_view_mode()

    def flip_horizontal(self):
        if not self.load_successful:
            return
        self._tf_flip_h = not self._tf_flip_h
        self._apply_transform_to_view()
        self._mark_dirty(True)
        if getattr(self.image_display_area, "_view_mode", "fit") in ("fit", "fit_width", "fit_height"):
            self.image_display_area.apply_current_view_mode()

    def flip_vertical(self):
        if not self.load_successful:
            return
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
                # Windows 10+ 환경에 최적화된 휴지통 삭제
                move_to_trash_windows(self.current_image_path)
                
                # 현재 이미지를 목록에서 제거
                if self.current_image_path in self.image_files_in_dir:
                    self.image_files_in_dir.remove(self.current_image_path)
                
                # 다음 이미지로 이동하거나 이전 이미지로 이동
                if self.image_files_in_dir:
                    # 인덱스 조정
                    if self.current_image_index >= len(self.image_files_in_dir):
                        self.current_image_index = len(self.image_files_in_dir) - 1
                    
                    # 새로운 이미지 로드
                    if self.current_image_index >= 0:
                        self.load_image(self.image_files_in_dir[self.current_image_index], source='nav')
                    else:
                        # 이미지가 없으면 화면 클리어
                        self.clear_display()
                else:
                    # 모든 이미지가 삭제되면 화면 클리어
                    self.clear_display()
                
                self.update_button_states()
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "삭제 오류",
                    f"파일을 삭제할 수 없습니다:\n{str(e)}"
                )

    # 삭제 기능은 delete_utils로 분리됨

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
            success = self.load_image(file_path, source='open')
            if success:
                try:
                    parent_dir = os.path.dirname(file_path)
                    if parent_dir and os.path.isdir(parent_dir):
                        self.last_open_dir = parent_dir
                        self.save_settings()
                except Exception:
                    pass

    def load_image(self, file_path, source='other'):
        # Dirty 체크 후 정책 실행
        if self._is_dirty and self.current_image_path and os.path.normcase(file_path) != os.path.normcase(self.current_image_path):
            if not self._handle_dirty_before_action():
                return False
        # 동기 로딩 경로
        path, img, success, _ = self.image_service.load(file_path)
        if success and img is not None:
            self._apply_loaded_image(path, img, source)
            return True
        # 실패 처리
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
            pix = self.image_display_area.originalPixmap()
            if not pix or pix.isNull():
                return False
            img = pix.toImage()
            ok, err = self.image_service.save_with_transform(
                img,
                self.current_image_path,
                self.current_image_path,
                self._tf_rotation,
                self._tf_flip_h,
                self._tf_flip_v,
                quality=self._jpeg_quality,
            )
            if not ok:
                QMessageBox.critical(self, "저장 오류", err or "파일 저장에 실패했습니다.")
                return False
            # 저장 후 재로드 및 상태 리셋
            self.load_image(self.current_image_path, source='save')
            self._mark_dirty(False)
            return True
        except Exception as e:
            QMessageBox.critical(self, "저장 오류", str(e))
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

    def open_shortcuts_help(self):
        dlg = ShortcutsHelpDialog(self)
        dlg.exec()

    def scan_directory(self, dir_path):
        self.image_files_in_dir, self.current_image_index = self.image_service.scan_directory(dir_path, self.current_image_path)
        self.update_button_states()
        self.update_status_left()

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
            self.save_last_session()
        except Exception:
            pass
        super().closeEvent(event)