import os
import sys
import ctypes # Windows 전용
import functools
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtGui import QPixmap

SUPPORTED_FORMATS = [".jpeg", ".jpg", ".png", ".bmp", ".gif", ".tiff"]

if sys.platform == "win32":  # Windows
    try:
        shlwapi = ctypes.WinDLL('shlwapi')
        strcmplogicalw_func = shlwapi.StrCmpLogicalW
        strcmplogicalw_func.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        strcmplogicalw_func.restype = ctypes.c_int
    except OSError:
        print("경고: shlwapi.dll을 로드할 수 없어 기본 정렬을 사용합니다.")
        strcmplogicalw_func = None
else:  # Windows가 아닌 OS
    strcmplogicalw_func = None

def windows_style_sort_key(item1, item2):
    """ StrCmpLogicalW를 사용한 비교 함수, 실패 시 기본 비교 """
    if strcmplogicalw_func:
        return strcmplogicalw_func(item1, item2)
    if item1 < item2: return -1
    if item1 > item2: return 1
    return 0

def open_file_dialog_util(parent_widget, initial_dir=None):
    file_filter = f"사진 ({' '.join(['*' + ext for ext in SUPPORTED_FORMATS])})"
    start_dir = initial_dir if (initial_dir and os.path.isdir(initial_dir)) else ""
    file_path, _ = QFileDialog.getOpenFileName(parent_widget, "사진 파일 열기", start_dir, file_filter)
    return file_path

def load_image_util(file_path, image_display_area):
    if not file_path:
        print("이미지를 선택하지 않았습니다.")
        return None, False

    pixmap = QPixmap(file_path)
    if pixmap.isNull():
        print(f"오류: 이미지를 불러올 수 없습니다. {file_path}")
        image_display_area.setPixmap(None)
        return None, False
    
    image_display_area.setPixmap(pixmap)
    return file_path, True

def scan_directory_util(dir_path, current_image_path):
    image_files_in_dir = []
    current_image_index = -1
    
    normalized_current_path = None
    if current_image_path:
        normalized_current_path = os.path.normcase(current_image_path)

    try:
        raw_files = os.listdir(dir_path)
        if strcmplogicalw_func:  # Windows 정렬 사용 가능 시
            sorted_filenames = sorted(raw_files, key=functools.cmp_to_key(windows_style_sort_key))
        else:  # 그 외의 경우 기본 정렬
            sorted_filenames = sorted(raw_files)
        
        temp_file_list = []
        for fname in sorted_filenames:
            if os.path.splitext(fname.lower())[1] in SUPPORTED_FORMATS:
                full_path = os.path.join(dir_path, fname)
                temp_file_list.append(full_path)
                if normalized_current_path and os.path.normcase(full_path) == normalized_current_path:
                    current_image_index = len(temp_file_list) - 1
        
        image_files_in_dir = temp_file_list

        if current_image_index == -1 and current_image_path and image_files_in_dir:
            print(f"경고: 현재 로드된 이미지 '{current_image_path}'를 해당 디렉토리의 스캔 목록에서 정확히 찾지 못했습니다.")

    except OSError as e:
        print(f"디렉토리 스캔 중 오류 발생: {e}")
        return [], -1 
    
    return image_files_in_dir, current_image_index 