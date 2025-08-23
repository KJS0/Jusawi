import os


def move_to_trash_windows(file_path):
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
                ("lpszProgressTitle", wintypes.LPCWSTR),
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
                "powershell",
                "-Command",
                f"Add-Type -AssemblyName Microsoft.VisualBasic; "
                f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
                f"'{file_path}', 'OnlyErrorDialogs', 'SendToRecycleBin')",
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        except Exception as ps_error:
            raise Exception(f"모든 휴지통 삭제 방법 실패. Windows API: {e}, PowerShell: {ps_error}")


