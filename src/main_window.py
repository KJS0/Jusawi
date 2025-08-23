import os
import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QApplication, QMainWindow, QLabel, QSizePolicy
from PyQt6.QtCore import QTimer, Qt, QEvent
from PyQt6.QtGui import QKeySequence, QShortcut, QImage

from .image_view import ImageView
from .file_utils import open_file_dialog_util, load_image_util, scan_directory_util

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

        # QMainWindow의 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # 중앙 영역 배경을 #373737로 통일
        central_widget.setStyleSheet("background-color: #373737;")
        
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self._normal_margins = (5, 5, 5, 5)

        # ImageView (QGraphicsView 기반)
        self.image_display_area = ImageView(central_widget)
        self.image_display_area.scaleChanged.connect(self.on_scale_changed)
        self.image_display_area.cursorPosChanged.connect(self.on_cursor_pos_changed)
        # 명시적 min/max 스케일 설정
        self.image_display_area.set_min_max_scale(self.min_scale, self.max_scale)
        self.main_layout.addWidget(self.image_display_area, 1)

        self.button_layout = QHBoxLayout()
        self.open_button = QPushButton("열기")
        self.open_button.clicked.connect(self.open_file)

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
            self.fullscreen_button,
            self.prev_button,
            self.next_button,
            self.zoom_out_button,
            self.fit_button,
            self.zoom_in_button,
        ]:
            btn.setStyleSheet(button_style)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 버튼 순서: 열기 전체화면 이전 다음 축소 100% 확대
        self.button_layout.addWidget(self.open_button)
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
        self.update_status_left()
        self.update_status_right()

        # 키보드 단축키 설정
        self.setup_shortcuts()
        
        # 이미지 라벨에 초기 포커스 설정
        self.image_display_area.setFocus()
        
        self.update_button_states()

    def clamp(self, value, min_v, max_v):
        return max(min_v, min(value, max_v))

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
                        self.load_image(self.image_files_in_dir[self.current_image_index])
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
        file_path = open_file_dialog_util(self)
        if file_path:
            self.load_image(file_path)

    def load_image(self, file_path):
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
            self.load_image(self.image_files_in_dir[self.current_image_index])

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
        return super().eventFilter(obj, event)