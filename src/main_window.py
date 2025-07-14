import os
import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QApplication, QMainWindow
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QKeySequence, QShortcut

from .image_label import ImageLabel
from .file_utils import open_file_dialog_util, load_image_util, scan_directory_util

class JusawiViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jusawi")

        self.current_image_path = None
        self.image_files_in_dir = []
        self.current_image_index = -1
        self.load_successful = False
        
        # 전체화면 및 슬라이드쇼 상태 관리
        self.is_fullscreen = False
        self.is_slideshow_active = False
        self.button_layout = None  # 나중에 설정
        self.previous_window_state = None  # 전체화면 이전 상태 저장

        # QMainWindow의 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self.image_display_area = ImageLabel(central_widget)
        main_layout.addWidget(self.image_display_area, 1)

        self.button_layout = QHBoxLayout()
        self.open_button = QPushButton("열기")
        self.open_button.clicked.connect(self.open_file)

        self.prev_button = QPushButton("이전")
        self.next_button = QPushButton("다음")
        self.prev_button.clicked.connect(self.show_prev_image)
        self.next_button.clicked.connect(self.show_next_image)
        
        self.button_layout.addWidget(self.open_button)
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.prev_button)
        self.button_layout.addWidget(self.next_button)

        main_layout.addLayout(self.button_layout)

        # 키보드 단축키 설정
        self.setup_shortcuts()
        
        # 이미지 라벨에 초기 포커스 설정
        self.image_display_area.setFocus()
        
        self.update_button_states()

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
        
        # 버튼 레이아웃 먼저 숨기기
        for i in range(self.button_layout.count()):
            widget = self.button_layout.itemAt(i).widget()
            if widget:
                widget.hide()
        
        # 직접 전체화면으로 전환 (애니메이션 최소화)
        self.showFullScreen()

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
        for i in range(self.button_layout.count()):
            widget = self.button_layout.itemAt(i).widget()
            if widget:
                widget.show()

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
        self.update_button_states()
        return success

    def scan_directory(self, dir_path):
        self.image_files_in_dir, self.current_image_index = scan_directory_util(dir_path, self.current_image_path)
        self.update_button_states()

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