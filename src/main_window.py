import os
import sys
import ctypes # Windows 전용
import functools
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QPushButton
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QTimer

from .image_label import ImageLabel

if sys.platform == "win32": # Windows
    try:
        shlwapi = ctypes.WinDLL('shlwapi')
        strcmplogicalw_func = shlwapi.StrCmpLogicalW
        strcmplogicalw_func.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        strcmplogicalw_func.restype = ctypes.c_int
    except OSError:
        print("경고: shlwapi.dll을 로드할 수 없어 기본 정렬을 사용합니다.")
        strcmplogicalw_func = None
else: # Windows가 아닌 OS
    strcmplogicalw_func = None

def windows_style_sort_key(item1, item2):
    """ StrCmpLogicalW를 사용한 비교 함수, 실패 시 기본 비교 """
    if strcmplogicalw_func:
        return strcmplogicalw_func(item1, item2)
    if item1 < item2: return -1
    if item1 > item2: return 1
    return 0

class JusawiViewer(QWidget):
    SUPPORTED_FORMATS = [".jpeg", ".jpg", ".png", ".bmp", ".gif", ".tiff"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jusawi")

        self.current_image_path = None
        self.image_files_in_dir = []
        self.current_image_index = -1
        self.load_successful = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self.image_display_area = ImageLabel(self)
        main_layout.addWidget(self.image_display_area, 1)

        button_layout = QHBoxLayout()
        self.prev_button = QPushButton("이전")
        self.next_button = QPushButton("다음")
        self.prev_button.clicked.connect(self.show_prev_image)
        self.next_button.clicked.connect(self.show_next_image)
        
        button_layout.addStretch(1)
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.next_button)
        button_layout.addStretch(1)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

        self.update_button_states()
        
        self.load_successful = self.open_file_dialog()
        if not self.load_successful:
            QTimer.singleShot(0, self.close)


    def open_file_dialog(self):
        file_filter = f"사진 ({' '.join(['*' + ext for ext in self.SUPPORTED_FORMATS])})"
        file_path, _ = QFileDialog.getOpenFileName(self, "사진 파일 열기", "", file_filter)

        if file_path:
            return self.load_image(file_path)
        else:
            print("이미지를 선택하지 않았습니다. 프로그램을 종료합니다.")
            return False

    def load_image(self, file_path):
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            print(f"오류: 이미지를 불러올 수 없습니다. {file_path}")
            self.image_display_area.setPixmap(None)
            self.current_image_path = None
            self.image_files_in_dir = []
            self.current_image_index = -1
            self.update_button_states()
            return False
        
        self.image_display_area.setPixmap(pixmap)
        self.current_image_path = file_path
        if os.path.exists(file_path):
             self.scan_directory(os.path.dirname(file_path))
        return True

    def scan_directory(self, dir_path):
        self.image_files_in_dir = []
        new_index = -1
        
        normalized_current_path = None
        if self.current_image_path:
            normalized_current_path = os.path.normcase(self.current_image_path)

        try:
            raw_files = os.listdir(dir_path)
            if strcmplogicalw_func: # Windows 정렬 사용 가능 시
                sorted_filenames = sorted(raw_files, key=functools.cmp_to_key(windows_style_sort_key))
            else: # 그 외의 경우 기본 정렬
                sorted_filenames = sorted(raw_files) 
            
            temp_file_list = []
            for fname in sorted_filenames:
                if os.path.splitext(fname.lower())[1] in self.SUPPORTED_FORMATS:
                    full_path = os.path.join(dir_path, fname)
                    temp_file_list.append(full_path)
                    if normalized_current_path and os.path.normcase(full_path) == normalized_current_path:
                        new_index = len(temp_file_list) - 1
            
            self.image_files_in_dir = temp_file_list
            self.current_image_index = new_index

            if self.current_image_index == -1 and self.current_image_path and self.image_files_in_dir:
                print(f"경고: 현재 로드된 이미지 '{self.current_image_path}'를 해당 디렉토리의 스캔 목록에서 정확히 찾지 못했습니다.")

        except OSError as e:
            print(f"디렉토리 스캔 중 오류 발생: {e}")
            self.image_files_in_dir = []
            self.current_image_index = -1
        
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