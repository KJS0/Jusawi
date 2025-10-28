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

from .logging_setup import get_logger
log = get_logger("utils.file")

SUPPORTED_FORMATS = [".jpeg", ".jpg", ".png", ".bmp", ".gif", ".tiff", ".webp"]

if sys.platform == "win32":  # Windows
    try:
        shlwapi = ctypes.WinDLL('shlwapi')
        strcmplogicalw_func = shlwapi.StrCmpLogicalW
        strcmplogicalw_func.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        strcmplogicalw_func.restype = ctypes.c_int
    except OSError:
        try:
            log.warning("shlwapi_load_failed_fallback_sort")
        except Exception:
            pass
        strcmplogicalw_func = None
else:  # Windows가 아닌 OS
    strcmplogicalw_func = None

def windows_style_sort_key(item1, item2):
    """Windows 탐색기(논리) 정렬 비교 함수.
    - 가능하면 StrCmpLogicalW 사용
    - 불가 시 숫자를 숫자처럼 비교하는 자연 정렬로 폴백(대소문자 무시)
    """
    if strcmplogicalw_func:
        try:
            return int(strcmplogicalw_func(item1, item2))
        except Exception:
            pass
    # 폴백: 숫자 인식 자연 비교 (case-insensitive)
    try:
        import re
        def _tokenize(s: str):
            parts = re.split(r'(\d+)', s or '')
            out = []
            for p in parts:
                if p.isdigit():
                    try:
                        out.append(int(p))
                    except Exception:
                        out.append(p)
                else:
                    out.append(p.lower())
            return out
        a = _tokenize(item1)
        b = _tokenize(item2)
        # 순차 비교
        for x, y in zip(a, b):
            if x == y:
                continue
            if isinstance(x, int) and isinstance(y, int):
                return -1 if x < y else 1
            # str vs int 또는 str vs str
            xs = str(x)
            ys = str(y)
            if xs < ys:
                return -1
            if xs > ys:
                return 1
            # 동일 처리
        # 길이 비교
        if len(a) < len(b):
            return -1
        if len(a) > len(b):
            return 1
    except Exception:
        pass
    # 최종 폴백: 단순 사전식(CI)
    s1 = (item1 or '').lower()
    s2 = (item2 or '').lower()
    if s1 < s2: return -1
    if s1 > s2: return 1
    return 0

def open_file_dialog_util(parent_widget, initial_dir=None):
    file_filter = f"사진 ({' '.join(['*' + ext for ext in SUPPORTED_FORMATS])})"
    start_dir = initial_dir if (initial_dir and os.path.isdir(initial_dir)) else ""
    file_path, _ = QFileDialog.getOpenFileName(parent_widget, "사진 파일 열기", start_dir, file_filter)
    return file_path

def load_image_util(file_path, image_display_area):
    if not file_path:
        log.info("open_dialog_empty_selection")
        return None, False

    pixmap = QPixmap(file_path)
    if pixmap.isNull():
        log.error("qpixmap_load_fail | file=%s", os.path.basename(file_path))
        image_display_area.setPixmap(None)
        return None, False
    
    image_display_area.setPixmap(pixmap)
    log.info("qpixmap_load_ok | file=%s | w=%d | h=%d", os.path.basename(file_path), int(pixmap.width()), int(pixmap.height()))
    return file_path, True

def _is_hidden_or_system(path: str) -> bool:
    try:
        name = os.path.basename(path)
        if name.startswith('.'):
            return True
        # Windows 시스템/숨김 속성 검사(가능한 경우)
        if sys.platform == "win32":
            try:
                import ctypes
                FILE_ATTRIBUTE_HIDDEN = 0x2
                FILE_ATTRIBUTE_SYSTEM = 0x4
                attrs = ctypes.windll.kernel32.GetFileAttributesW(ctypes.c_wchar_p(path))
                if attrs != -1 and (attrs & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)):
                    return True
            except Exception:
                pass
        return False
    except Exception:
        return False


def scan_directory_util(dir_path, current_image_path):
    image_files_in_dir = []
    current_image_index = -1

    normalized_current_path = os.path.normcase(current_image_path) if current_image_path else None

    try:
        raw_files = os.listdir(dir_path)
        # 1차: 파일명 정렬(Windows 논리 정렬 우선) - 설정에 따라 자연/사전식 선택은 상위에서 처리 가능
        if strcmplogicalw_func:
            sorted_filenames = sorted(raw_files, key=functools.cmp_to_key(windows_style_sort_key))
        else:
            sorted_filenames = sorted(raw_files)

        # 후보 파일 수집
        temp_files = []
        for fname in sorted_filenames:
            if os.path.splitext(fname.lower())[1] in SUPPORTED_FORMATS:
                full = os.path.join(dir_path, fname)
                temp_files.append(full)

        # 2차: 정렬 키 계산 (우선순위 기반: EXIF/mtime/name)
        def _exif_ts(p: str):
            try:
                # Pillow 기반 초경량 EXIF 추출 (실패 시 None)
                from ..services.exif_utils import extract_with_pillow  # type: ignore
                meta = extract_with_pillow(p) or {}
                dt = meta.get("DateTimeOriginal") or meta.get("DateTime")
                if isinstance(dt, str) and len(dt) >= 19 and dt[4] == ":":
                    y, mo, d = int(dt[0:4]), int(dt[5:7]), int(dt[8:10])
                    hh, mm, ss = int(dt[11:13]), int(dt[14:16]), int(dt[17:19])
                    import datetime
                    return datetime.datetime(y, mo, d, hh, mm, ss).timestamp()
            except Exception:
                return None
        def _mtime(p: str) -> float:
            try:
                st = os.stat(p)
                return float(st.st_mtime)
            except Exception:
                return 0.0
        def _name(p: str) -> str:
            return os.path.basename(p).lower()
        def _sort_key(p: str):
            # 우선순위는 호출자(viewer)의 설정을 통해 services.image_service에서 재정렬되므로,
            # 여기서는 기본(메타데이터 우선) 키 구성을 유지(폴백 로직도 포함)
            exif_ts = _exif_ts(p)
            mt = _mtime(p)
            return (
                exif_ts if exif_ts is not None else float("inf"),
                mt if exif_ts is None else 0.0,
                _name(p),
            )

        try:
            temp_files.sort(key=_sort_key)
        except Exception:
            # EXIF 정렬 실패 시 파일명 정렬로 폴백
            temp_files.sort(key=lambda p: os.path.basename(p).lower())

        image_files_in_dir = temp_files

        if normalized_current_path:
            for i, full in enumerate(image_files_in_dir):
                if os.path.normcase(full) == normalized_current_path:
                    current_image_index = i
                    break

        if current_image_index == -1 and current_image_path and image_files_in_dir:
            log.warning("scan_dir_missing_current | current=%s", os.path.basename(current_image_path))

    except OSError as e:
        log.error("scan_dir_os_error | dir=%s | err=%s", os.path.basename(dir_path or ""), str(e))
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