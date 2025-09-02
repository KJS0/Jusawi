import os
from .logging_setup import get_logger
log = get_logger("utils.delete")


def move_to_trash_windows(file_path):
    """Windows 10+ 환경용 휴지통 이동"""
    import time
    last_error: Exception | None = None

    # 최대 3회 재시도 (스캐너/인덱서의 일시적 잠금 회피)
    for attempt in range(3):
        try:
            # 경로 정규화 (send2trash 호환성 향상)
            normalized_path = os.path.normpath(file_path)

            # 먼저 send2trash 시도
            try:
                import send2trash
                send2trash.send2trash(normalized_path)
                log.info("trash_ok_send2trash | file=%s | attempt=%d", os.path.basename(file_path), attempt + 1)
                return
            except ImportError:
                # 모듈 없으면 다음 단계로
                pass
            except Exception as e:
                # send2trash 실패 → 다음 단계로
                last_error = e

            # Windows API 직접 사용 (SHFileOperationW)
            try:
                import ctypes
                from ctypes import wintypes

                shell32 = ctypes.windll.shell32

                # SHFILEOPSTRUCT 정의
                class SHFILEOPSTRUCT(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", wintypes.HWND),
                        ("wFunc", wintypes.UINT),
                        ("pFrom", wintypes.LPCWSTR),
                        ("pTo", wintypes.LPCWSTR),
                        ("fFlags", wintypes.WORD),
                        ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", wintypes.LPVOID),
                        ("lpszProgressTitle", wintypes.LPCWSTR),
                    ]

                FO_DELETE = 0x0003
                FOF_ALLOWUNDO = 0x0040
                FOF_NOCONFIRMATION = 0x0010
                FOF_SILENT = 0x0004

                # pFrom은 이중 NUL 종료여야 함
                pfrom = os.path.normpath(file_path) + "\0\0"

                fileop = SHFILEOPSTRUCT()
                fileop.hwnd = 0
                fileop.wFunc = FO_DELETE
                fileop.pFrom = pfrom
                fileop.pTo = None
                fileop.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
                fileop.fAnyOperationsAborted = False
                fileop.hNameMappings = None
                fileop.lpszProgressTitle = None

                result = shell32.SHFileOperationW(ctypes.byref(fileop))
                if result == 0:
                    log.info("trash_ok_shell | file=%s | attempt=%d", os.path.basename(file_path), attempt + 1)
                    return
                last_error = Exception(f"SHFileOperationW 실패: 오류 코드 {result}")
            except Exception as e2:
                last_error = e2

            # PowerShell 경로 폴백
            try:
                import subprocess
                ps = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    (
                        "Add-Type -AssemblyName Microsoft.VisualBasic; "
                        "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
                        f"'{os.path.normpath(file_path)}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
                    ),
                ]
                subprocess.run(ps, check=True, capture_output=True)
                log.info("trash_ok_powershell | file=%s | attempt=%d", os.path.basename(file_path), attempt + 1)
                return
            except Exception as e3:
                last_error = e3
        except Exception as e:
            last_error = e

        # 재시도 대기 (지수 백오프)
        time.sleep(0.1 * (2 ** attempt))

    # 모든 방법 실패
    log.error("trash_fail | file=%s | err=%s", os.path.basename(file_path), str(last_error))
    raise Exception(f"휴지통 이동 실패: {last_error}")


