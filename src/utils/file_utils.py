import os
import sys
import ctypes # Windows 전용
import functools
import uuid
import shutil
import tempfile
import time
from typing import Optional, Tuple
from PyQt6.QtWidgets import QFileDialog  # type: ignore[import]
from PyQt6.QtGui import QPixmap  # type: ignore[import]

SUPPORTED_FORMATS = [".jpeg", ".jpg", ".png", ".bmp", ".gif", ".tiff", ".webp"]

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


# ----- 안전 저장 유틸 -----

def _create_temp_sibling(target_path: str) -> str:
    base_dir = os.path.dirname(target_path) or os.getcwd()
    unique = uuid.uuid4().hex
    # 동일 볼륨/디렉터리에 생성해야 원자 교체 가능
    return os.path.join(base_dir, f".{os.path.basename(target_path)}.tmp-{unique}")


def _flush_file_descriptor(fobj) -> None:
    try:
        fobj.flush()
    except Exception:
        pass
    try:
        os.fsync(fobj.fileno())
    except Exception:
        # Windows에서는 FlushFileBuffers로 대체됨
        try:
            import msvcrt
            msvcrt.get_osfhandle(fobj.fileno())
        except Exception:
            pass


def _replace_file_windows(target_path: str, temp_path: str, backup_path: Optional[str]) -> None:
    # ReplaceFileW 사용
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    ReplaceFileW = kernel32.ReplaceFileW
    ReplaceFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    ReplaceFileW.restype = ctypes.c_int

    REPLACEFILE_WRITE_THROUGH = 0x00000001
    lpReplacedFileName = ctypes.c_wchar_p(target_path)
    lpReplacementFileName = ctypes.c_wchar_p(temp_path)
    lpBackupFileName = ctypes.c_wchar_p(backup_path) if backup_path else None
    res = ReplaceFileW(lpReplacedFileName, lpReplacementFileName, lpBackupFileName, REPLACEFILE_WRITE_THROUGH, None, None)
    if res == 0:
        # 실패 시 Win32 오류 메시지 포함
        err = ctypes.GetLastError()
        raise OSError(err, f"ReplaceFileW 실패 (code={err})")


def _atomic_replace(target_path: str, temp_path: str, create_backup: bool = True) -> Tuple[bool, str, Optional[str]]:
    """
    temp_path를 target_path로 원자적으로 교체. Windows에서는 ReplaceFileW, POSIX에서는 rename 사용.
    반환: (성공 여부, 오류 메시지, 백업 경로)
    """
    backup_path: Optional[str] = None
    try:
        if sys.platform == "win32":
            if create_backup and os.path.exists(target_path):
                backup_path = target_path + ".bak"
            _replace_file_windows(target_path, temp_path, backup_path)
        else:
            # 동일 파일시스템 전제. 이미 같은 디렉터리에 생성하므로 rename은 원자적
            if create_backup and os.path.exists(target_path):
                backup_path = target_path + ".bak"
                shutil.copy2(target_path, backup_path)
            os.replace(temp_path, target_path)
        return True, "", backup_path
    except Exception as e:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        return False, str(e), backup_path


def safe_write_bytes(target_path: str, data: bytes, write_through: bool = True, retries: int = 5) -> Tuple[bool, str]:
    """
    안전 저장: 임시 파일에 기록 후 플러시/동기화, 그 다음 원자적 교체. 실패 시 자동 롤백.
    """
    temp_path = _create_temp_sibling(target_path)
    try:
        # 임시 파일에 쓰기
        with open(temp_path, "wb", buffering=0) as f:
            f.write(data)
            if write_through:
                _flush_file_descriptor(f)
        # 재시도 정책(잠금, 바이러스 스캐너 등)
        delay = 0.05
        for i in range(max(1, int(retries))):
            ok, err, backup = _atomic_replace(target_path, temp_path, create_backup=True)
            if ok:
                # 교체 성공 후 디렉터리 엔트리까지 동기화 시도(가능한 경우)
                try:
                    dir_fd = os.open(os.path.dirname(target_path) or ".", os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except Exception:
                    pass
                # 백업은 유지(비정상 종료 대비). 추후 클린업 루틴에서 정리.
                return True, ""
            # 실패 시 지수 백오프 후 재시도
            time.sleep(delay)
            delay = min(1.0, delay * 2)
        return False, err if 'err' in locals() else "원자적 교체 실패"
    except Exception as e:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        return False, str(e)


def cleanup_leftover_temp_and_backup(directory: str, max_age_seconds: int = 7 * 24 * 3600) -> None:
    """비정상 종료로 남은 .tmp-*, .bak 파일을 정리"""
    now = time.time()
    try:
        for name in os.listdir(directory):
            if name.endswith('.bak') or '.tmp-' in name:
                path = os.path.join(directory, name)
                try:
                    st = os.stat(path)
                    if now - st.st_mtime >= max_age_seconds:
                        os.remove(path)
                except Exception:
                    pass
    except Exception:
        pass