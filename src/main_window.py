import os
import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QApplication, QMainWindow, QLabel, QSizePolicy, QMenu
from PyQt6.QtCore import QTimer, Qt, QEvent, QUrl, QSettings, QPointF
from PyQt6.QtGui import QKeySequence, QShortcut, QImage, QAction

from .image_view import ImageView
from .file_utils import open_file_dialog_util, load_image_util, scan_directory_util, SUPPORTED_FORMATS

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

        self.button_layout = QHBoxLayout()
        self.open_button = QPushButton("열기")
        self.open_button.clicked.connect(self.open_file)
        # 최근 메뉴를 별도 버튼에 연결
        self.recent_menu = QMenu(self)
        self.recent_button = QPushButton("최근 파일")
        self.recent_button.setMenu(self.recent_menu)

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

        # 상단 버튼 텍스트 색 적용 및 창 크기에 비례하지 않도록 고정 크기 정책 설정
        button_style = "color: #EAEAEA;"
        for btn in [
            self.open_button,
            self.recent_button,
            self.fullscreen_button,
            self.prev_button,
            self.next_button,
            self.zoom_out_button,
            self.fit_button,
            self.zoom_in_button,
        ]:
            btn.setStyleSheet(button_style)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 버튼 순서: 열기 최근 전체화면 이전 다음 축소 100% 확대
        self.button_layout.addWidget(self.open_button)
        self.button_layout.addWidget(self.recent_button)
        self.button_layout.addWidget(self.fullscreen_button)
        self.button_layout.addWidget(self.prev_button)
        self.button_layout.addWidget(self.next_button)
        self.button_layout.addWidget(self.zoom_out_button)
        self.button_layout.addWidget(self.fit_button)
        self.button_layout.addWidget(self.zoom_in_button)
        # 남는 공간을 스트레치로 채워 버튼이 확장되지 않도록 함
        self.button_layout.addStretch(1)

        # 버튼 바 컨테이너(투명 배경 유지)
        self.button_bar = QWidget()
        self.button_bar.setStyleSheet("background-color: transparent; QPushButton { color: #EAEAEA; }")
        self.button_bar.setLayout(self.button_layout)
        self.main_layout.insertWidget(0, self.button_bar)

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

    def clamp(self, value, min_v, max_v):
        return max(min_v, min(value, max_v))

    def _enable_dnd_on(self, widget):
        try:
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)
        except Exception:
            pass

    def _setup_global_dnd(self):
        widgets = [
            self.centralWidget(),
            self.button_bar,
            self.open_button, self.recent_button, self.fullscreen_button, self.prev_button, self.next_button,
            self.zoom_out_button, self.fit_button, self.zoom_in_button,
            self.image_display_area,
            getattr(self.image_display_area, 'viewport', lambda: None)(),
            self.statusBar(), self.status_left_label, self.status_right_label,
        ]
        for w in widgets:
            if w:
                self._enable_dnd_on(w)

    # Settings: 저장/로드
    def load_settings(self):
        try:
            self.recent_files = self.settings.value("recent/files", [], list)
            self.recent_folders = self.settings.value("recent/folders", [], list)
            if not isinstance(self.recent_files, list): self.recent_files = []
            if not isinstance(self.recent_folders, list): self.recent_folders = []
            self.last_open_dir = self.settings.value("recent/last_open_dir", "", str)
            if not isinstance(self.last_open_dir, str): self.last_open_dir = ""
        except Exception:
            self.recent_files = []
            self.recent_folders = []
            self.last_open_dir = ""

    def save_settings(self):
        try:
            self.settings.setValue("recent/files", self.recent_files)
            self.settings.setValue("recent/folders", self.recent_folders)
            self.settings.setValue("recent/last_open_dir", self.last_open_dir)
        except Exception:
            pass

    # 최근 항목: 유틸
    def _normalize_path(self, p: str) -> str:
        try:
            return os.path.normcase(os.path.normpath(p))
        except Exception:
            return p

    def _update_mru(self, mru_list: list, path: str, max_items: int = 10) -> list:
        norm = self._normalize_path(path)
        filtered = []
        seen = set()
        for it in mru_list:
            ip = it.get("path", "") if isinstance(it, dict) else str(it)
            key = self._normalize_path(ip)
            if key and key != norm and key not in seen:
                filtered.append({"path": ip})
                seen.add(key)
        filtered.insert(0, {"path": path})
        return filtered[:max_items]

    def rebuild_recent_menu(self):
        self.recent_menu.clear()
        # 최근 파일만 표시
        if self.recent_files:
            for item in self.recent_files:
                path = item.get("path") if isinstance(item, dict) else str(item)
                act = QAction(os.path.basename(path), self)
                act.setToolTip(path)
                act.triggered.connect(lambda _, p=path: self.load_image(p, source='recent'))
                self.recent_menu.addAction(act)
            self.recent_menu.addSeparator()
        # 비우기 → 지우기
        clear_act = QAction("지우기", self)
        clear_act.triggered.connect(self.clear_recent)
        self.recent_menu.addAction(clear_act)

    def _open_recent_folder(self, dir_path: str):
        if not dir_path or not os.path.isdir(dir_path):
            self.statusBar().showMessage("폴더가 존재하지 않습니다.", 3000)
            # 존재하지 않는 항목은 목록에서 제거
            self.recent_folders = [it for it in self.recent_folders if self._normalize_path(it.get("path","")) != self._normalize_path(dir_path)]
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
    def _is_supported_image(self, path: str) -> bool:
        try:
            ext = os.path.splitext(path.lower())[1]
            return ext in SUPPORTED_FORMATS
        except Exception:
            return False

    def _handle_dropped_files(self, files):
        # 드롭 순서 유지 + 중복 제거 + 확장자 필터
        seen = set()
        clean_files = []
        for p in files:
            if (p not in seen) and self._is_supported_image(p):
                seen.add(p)
                clean_files.append(p)
        if not clean_files:
            self.statusBar().showMessage("지원하는 이미지 파일이 없습니다.", 3000)
            return
        self.image_files_in_dir = clean_files
        self.current_image_index = 0
        self.load_image(self.image_files_in_dir[self.current_image_index], source='drop')
        # 최근 파일 갱신 제거
        try:
            pass
        except Exception:
            pass

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
        paths = []
        for u in urls:
            if isinstance(u, QUrl) and u.isLocalFile():
                paths.append(u.toLocalFile())
        if not paths:
            event.ignore()
            return
        files = [p for p in paths if os.path.isfile(p)]
        if files:
            self._handle_dropped_files(files)
        event.acceptProposedAction()

    def human_readable_size(self, size_bytes: int) -> str:
        try:
            b = float(size_bytes)
        except Exception:
            return "-"
        units = ["B", "KiB", "MiB", "GiB", "TiB"]
        i = 0
        while b >= 1024.0 and i < len(units) - 1:
            b /= 1024.0
            i += 1
        if i == 0:
            return f"{int(b)} {units[i]}"
        return f"{b:.2f} {units[i]}"

    def compute_display_bit_depth(self, img: QImage) -> int:
        try:
            fmt = img.format()
            if fmt in (QImage.Format.Format_RGB888, QImage.Format.Format_BGR888):
                return 24
            if fmt in (QImage.Format.Format_Grayscale8, QImage.Format.Format_Indexed8):
                return 8
            if fmt in (QImage.Format.Format_Mono, QImage.Format.Format_MonoLSB):
                return 1
            if fmt in (QImage.Format.Format_Grayscale16,):
                return 16
            if fmt in (QImage.Format.Format_RGBA64, QImage.Format.Format_RGBX64):
                return 64 if img.hasAlphaChannel() else 48
            d = img.depth()
            if d == 32 and not img.hasAlphaChannel():
                return 24
            return d
        except Exception:
            try:
                return img.depth()
            except Exception:
                return 0

    def update_status_left(self):
        if not self.load_successful or not self.current_image_path:
            self.status_left_label.setText("")
            return
        # index/total
        total = len(self.image_files_in_dir)
        idx_disp = self.current_image_index + 1 if 0 <= self.current_image_index < total else 0
        filename = os.path.basename(self.current_image_path)
        # size
        try:
            size_bytes = os.path.getsize(self.current_image_path)
            size_str = self.human_readable_size(size_bytes)
        except OSError:
            size_str = "-"
        # dimensions and depth
        w = h = depth = 0
        pix = self.image_display_area.originalPixmap()
        if pix and not pix.isNull():
            w = pix.width()
            h = pix.height()
            try:
                img = pix.toImage()
                depth = self.compute_display_bit_depth(img)
            except Exception:
                depth = 0
        dims = f"{w}*{h}*{depth}"
        self.status_left_label.setText(f"{idx_disp}/{total} {filename} {size_str} {dims}")

    def update_status_right(self):
        percent = int(round(self._last_scale * 100))
        self.status_right_label.setText(f"X:{self._last_cursor_x}, Y:{self._last_cursor_y} {percent}%")

    def on_scale_changed(self, scale: float):
        self._last_scale = scale
        self.update_status_right()

    def on_cursor_pos_changed(self, x: int, y: int):
        self._last_cursor_x = x
        self._last_cursor_y = y
        self.update_status_right()

    # 세션 저장/복원
    def save_last_session(self):
        try:
            last = {
                "file_path": self.current_image_path or "",
                "dir_path": os.path.dirname(self.current_image_path) if self.current_image_path else "",
                "view_mode": getattr(self.image_display_area, "_view_mode", self._last_view_mode),
                "scale": float(self._last_scale or 1.0),
                "fullscreen": bool(self.is_fullscreen),
                "window_geometry": self.saveGeometry(),
            }
            self.settings.setValue("session/last", last)
            self.save_settings()
        except Exception:
            pass

    def restore_last_session(self):
        try:
            last = self.settings.value("session/last", {}, dict)
            if not isinstance(last, dict):
                return
            fpath = last.get("file_path") or ""
            dpath = last.get("dir_path") or ""
            vmode = last.get("view_mode") or 'fit'
            scale = float(last.get("scale") or 1.0)
            if fpath and os.path.isfile(fpath):
                self.load_image(fpath, source='restore')
            elif dpath and os.path.isdir(dpath):
                self.scan_directory(dpath)
                if 0 <= self.current_image_index < len(self.image_files_in_dir):
                    self.load_image(self.image_files_in_dir[self.current_image_index], source='restore')
            # 보기 모드/배율 적용
            if vmode == 'fit':
                self.image_display_area.fit_to_window()
            elif vmode == 'fit_width':
                self.image_display_area.fit_to_width()
            elif vmode == 'fit_height':
                self.image_display_area.fit_to_height()
            elif vmode == 'actual':
                self.image_display_area.reset_to_100()
            # scale은 free 모드에서만 유효
            if vmode == 'free' and self.image_display_area:
                self.image_display_area.set_absolute_scale(scale)
            # 창 지오메트리 복원
            try:
                geom = last.get("window_geometry")
                if geom:
                    self.restoreGeometry(geom)
            except Exception:
                pass
        except Exception:
            pass

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
        if file_path and os.path.exists(file_path):
            filename = os.path.basename(file_path)
            self.setWindowTitle(f"{filename} - Jusawi")
        else:
            self.setWindowTitle("Jusawi")

    def setup_shortcuts(self):
        """키보드 단축키 설정"""
        # ← / → : 이전/다음 이미지
        QShortcut(QKeySequence("Left"), self, self.show_prev_image)
        QShortcut(QKeySequence("Right"), self, self.show_next_image)
        
        # Ctrl + O : 파일 열기
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_file)
        
        # F11 : 전체화면 토글
        QShortcut(QKeySequence("F11"), self, self.toggle_fullscreen)
        
        # Esc : 전체화면 종료 또는 프로그램 종료
        QShortcut(QKeySequence("Escape"), self, self.handle_escape)
        
        # Del : 현재 이미지 삭제
        QShortcut(QKeySequence("Delete"), self, self.delete_current_image)

        # 보기 모드 단축키
        QShortcut(QKeySequence("F"), self, self.fit_to_window)
        QShortcut(QKeySequence("W"), self, self.fit_to_width)
        QShortcut(QKeySequence("H"), self, self.fit_to_height)
        QShortcut(QKeySequence("1"), self, self.reset_to_100)

        # 주의: Ctrl +/-/0 단축키는 제거됨

    def toggle_fullscreen(self):
        """전체화면 모드 토글"""
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        """전체화면 모드 진입 (애니메이션 없이)"""
        # 현재 창 상태 저장
        self.previous_window_state = {
            'geometry': self.geometry(),
            'window_state': self.windowState(),
            'maximized': self.isMaximized()
        }
        
        self.is_fullscreen = True
        
        # 버튼 바 컨테이너 숨김
        if hasattr(self, 'button_bar') and self.button_bar:
            self.button_bar.hide()
        
        # 상태바 숨김
        self.statusBar().hide()
        
        # 레이아웃 마진 제거
        margins = self.main_layout.contentsMargins()
        self._normal_margins = (margins.left(), margins.top(), margins.right(), margins.bottom())
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        # 스크롤바(있다면) 숨김
        self.image_display_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.image_display_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 직접 전체화면으로 전환 (애니메이션 최소화)
        self.showFullScreen()
        QTimer.singleShot(0, lambda: self.image_display_area.fit_to_window())

    def exit_fullscreen(self):
        """전체화면 모드 종료 (제목표시줄 보장)"""
        self.is_fullscreen = False
        
        # 안전한 방법으로 창 상태 복원 (제목표시줄 보장)
        if self.previous_window_state and self.previous_window_state['maximized']:
            # 최대화 상태로 복원 (PyQt6 기본 메소드 사용)
            self.showMaximized()
        else:
            # 일반 창으로 복원
            self.showNormal()
            if self.previous_window_state:
                # 지오메트리 복원
                QTimer.singleShot(10, lambda: self.setGeometry(self.previous_window_state['geometry']))
        
        # 버튼 레이아웃 다시 표시
        if hasattr(self, 'button_bar') and self.button_bar:
            self.button_bar.show()
        
        # 상태바 표시
        self.statusBar().show()
        
        # 레이아웃 마진 복원
        try:
            l, t, r, b = self._normal_margins
            self.main_layout.setContentsMargins(l, t, r, b)
        except Exception:
            self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 스크롤바 정책 복원: 필요 시 자동
        self.image_display_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.image_display_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        QTimer.singleShot(0, lambda: self.image_display_area.fit_to_window())

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
                self.move_to_trash_windows(self.current_image_path)
                
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

    def move_to_trash_windows(self, file_path):
        """Windows 10+ 환경용 휴지통 이동"""
        try:
            # 경로 정규화 (send2trash 호환성 향상)
            normalized_path = os.path.normpath(file_path)
            
            # 먼저 send2trash 시도
            import send2trash
            send2trash.send2trash(normalized_path)
            return
        except ImportError:
            pass
        except Exception as e:
            print(f"send2trash 실패: {e}")
            # send2trash 실패 시 정규화된 경로로 Windows API 시도
            file_path = os.path.normpath(file_path)
        
        # send2trash 실패 시 Windows API 직접 사용
        try:
            import ctypes
            from ctypes import wintypes
            
            # Shell32.dll의 SHFileOperationW 함수 사용
            shell32 = ctypes.windll.shell32
            
            # 파일 경로를 더블 널 종료 문자열로 변환
            file_path_wide = file_path + '\0'
            
            # SHFILEOPSTRUCT 구조체 정의
            class SHFILEOPSTRUCT(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", wintypes.WORD),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID),
                    ("lpszProgressTitle", wintypes.LPCWSTR)
                ]
            
            # 상수 정의
            FO_DELETE = 0x0003
            FOF_ALLOWUNDO = 0x0040
            FOF_NOCONFIRMATION = 0x0010
            FOF_SILENT = 0x0004
            
            # 구조체 초기화
            fileop = SHFILEOPSTRUCT()
            fileop.hwnd = 0
            fileop.wFunc = FO_DELETE
            fileop.pFrom = file_path_wide
            fileop.pTo = None
            fileop.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
            fileop.fAnyOperationsAborted = False
            fileop.hNameMappings = None
            fileop.lpszProgressTitle = None
            
            # SHFileOperationW 호출
            result = shell32.SHFileOperationW(ctypes.byref(fileop))
            
            if result != 0:
                raise Exception(f"SHFileOperationW 실패: 오류 코드 {result}")
                
        except Exception as e:
            # 마지막 시도: PowerShell 사용
            try:
                import subprocess
                cmd = [
                    "powershell", "-Command",
                    f"Add-Type -AssemblyName Microsoft.VisualBasic; "
                    f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
                    f"'{file_path}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
                ]
                subprocess.run(cmd, check=True, capture_output=True)
            except Exception as ps_error:
                raise Exception(f"모든 휴지통 삭제 방법 실패. Windows API: {e}, PowerShell: {ps_error}")

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
        loaded_path, success = load_image_util(file_path, self.image_display_area)
        self.load_successful = success
        if not success:
            self.current_image_path = None
            self.image_files_in_dir = []
            self.current_image_index = -1
            self.update_window_title()
        else:
            self.current_image_path = loaded_path
            self.update_window_title(loaded_path)  # 제목 업데이트
            if os.path.exists(file_path):
                 self.scan_directory(os.path.dirname(file_path))
            # ImageView가 로드 시 자동 맞춤
            self.update_button_states()
        self.update_button_states()
        # 상태바 갱신
        self.update_status_left()
        self.update_status_right()
        # 최근 파일 업데이트: 오직 'open' 경로에서만
        if success and source in ('open', 'drop'):
            try:
                self.recent_files = self._update_mru(self.recent_files, loaded_path)
                parent_dir = os.path.dirname(loaded_path)
                if parent_dir and os.path.isdir(parent_dir):
                    self.last_open_dir = parent_dir
                self.save_settings()
                self.rebuild_recent_menu()
            except Exception:
                pass
        return success

    def scan_directory(self, dir_path):
        self.image_files_in_dir, self.current_image_index = scan_directory_util(dir_path, self.current_image_path)
        self.update_button_states()
        self.update_status_left()

    def show_prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.load_image_at_current_index()

    def show_next_image(self):
        if self.current_image_index < len(self.image_files_in_dir) - 1:
            self.current_image_index += 1
            self.load_image_at_current_index()

    def load_image_at_current_index(self):
        if 0 <= self.current_image_index < len(self.image_files_in_dir):
            self.load_image(self.image_files_in_dir[self.current_image_index], source='nav')

    def update_button_states(self):
        num_images = len(self.image_files_in_dir)
        is_valid_index = 0 <= self.current_image_index < num_images
        
        self.prev_button.setEnabled(is_valid_index and self.current_image_index > 0)
        self.next_button.setEnabled(is_valid_index and self.current_image_index < num_images - 1)
        # 줌 버튼 상태
        has_image = bool(self.load_successful)
        self.zoom_in_button.setEnabled(has_image)
        self.zoom_out_button.setEnabled(has_image)
        self.fit_button.setEnabled(has_image)

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
        et = event.type()
        if et in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            md = getattr(event, 'mimeData', None)
            if md and event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
            return False
        if et == QEvent.Type.Drop:
            md = getattr(event, 'mimeData', None)
            if not (md and event.mimeData().hasUrls()):
                return False
            urls = event.mimeData().urls()
            paths = []
            for u in urls:
                if isinstance(u, QUrl) and u.isLocalFile():
                    paths.append(u.toLocalFile())
            if not paths:
                return False
            files = [p for p in paths if os.path.isfile(p)]
            if files:
                self._handle_dropped_files(files)
            else:
                # 폴더 드롭은 비활성화
                self.statusBar().showMessage("이미지 파일만 드래그하여 열 수 있습니다.", 3000)
            event.acceptProposedAction()
            return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        try:
            self.save_last_session()
        except Exception:
            pass
        super().closeEvent(event)