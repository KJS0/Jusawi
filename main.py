import sys
import os
from PyQt6.QtWidgets import QApplication  # type: ignore[import]
from src.ui.main_window import JusawiViewer 

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 명령줄 인자: 파일 또는 폴더 경로 사전 파싱
    args = [a for a in sys.argv[1:] if a and not a.startswith('-')]
    skip_restore = bool(args)
    viewer = JusawiViewer(skip_session_restore=skip_restore)
    # 인자가 있는 경우에만 즉시 열기 시도
    try:
        opened = False  
        if args:
            for arg in args:
                path = os.path.abspath(os.path.expanduser(arg))
                if os.path.isfile(path):
                    # 파일 직접 열기
                    try:
                        viewer.load_image(path, source='open')
                        opened = True
                        break
                    except Exception:
                        pass
                elif os.path.isdir(path):
                    # 폴더 인자: 디렉터리 스캔 후 현재 인덱스 이미지 로드
                    try:
                        viewer.scan_directory(path)
                        if 0 <= viewer.current_image_index < len(viewer.image_files_in_dir):
                            viewer.load_image(viewer.image_files_in_dir[viewer.current_image_index], source='open')
                            opened = True
                            break
                    except Exception:
                        pass
        # 인자가 있었으나 모두 실패한 경우, 마지막 세션 복원 시도
        if args and not opened:
            try:
                viewer.restore_last_session()
            except Exception:
                pass
    except Exception:
        pass
    viewer.show()
    sys.exit(app.exec())