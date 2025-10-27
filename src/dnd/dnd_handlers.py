import os
from PyQt6.QtCore import QUrl

from ..utils.file_utils import SUPPORTED_FORMATS
from ..utils.logging_setup import get_logger

_log = get_logger("ui.dnd")


def _is_supported_image(path: str) -> bool:
    try:
        ext = os.path.splitext(path.lower())[1]
        return ext in SUPPORTED_FORMATS
    except Exception:
        return False


def handle_dropped_files(viewer, files: list[str]) -> None:
    # 드롭 순서 유지 + 중복 제거 + 확장자 필터
    seen = set()
    clean_files = []
    for p in files:
        if (p not in seen) and _is_supported_image(p):
            seen.add(p)
            clean_files.append(p)
    if not clean_files:
        try:
            _log.info("dnd_drop_rejected | reason=no_supported_images | n=%d", len(files or []))
        except Exception:
            pass
        viewer.statusBar().showMessage("지원하는 이미지 파일이 없습니다.", 3000)
        return
    try:
        _log.info("dnd_drop_accept | n=%d | first=%s", len(clean_files), os.path.basename(clean_files[0]))
    except Exception:
        pass
    # 대용량 확인
    try:
        if bool(getattr(viewer, "_drop_confirm_over_threshold", True)):
            th = int(getattr(viewer, "_drop_large_threshold", 500))
            if len(clean_files) >= max(1, th):
                try:
                    from PyQt6.QtWidgets import QMessageBox  # type: ignore[import]
                    res = QMessageBox.question(viewer, "대용량 드롭", f"파일 {len(clean_files)}개를 열까요?",
                                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                               QMessageBox.StandardButton.Yes)
                    if res != QMessageBox.StandardButton.Yes:
                        return
                except Exception:
                    pass
    except Exception:
        pass

    # 목록 구성 정책
    use_parent_scan = bool(getattr(viewer, "_drop_use_parent_scan", True))
    if use_parent_scan:
        try:
            import os
            parent_dir = os.path.dirname(clean_files[0])
            if parent_dir and os.path.isdir(parent_dir):
                viewer.scan_directory(parent_dir)
                # 첫 파일로 인덱스 이동
                try:
                    if clean_files[0] in (viewer.image_files_in_dir or []):
                        viewer.current_image_index = (viewer.image_files_in_dir or []).index(clean_files[0])
                except Exception:
                    pass
                viewer.load_image_at_current_index()
                return
        except Exception:
            pass

    # 기본: 드롭 파일만 목록으로 사용
    viewer.image_files_in_dir = clean_files
    viewer.current_image_index = 0
    viewer.load_image(viewer.image_files_in_dir[viewer.current_image_index], source='drop')


def urls_to_local_files(urls) -> list[str]:
    if not urls:
        return []
    paths = []
    for u in urls:
        if isinstance(u, QUrl) and u.isLocalFile():
            paths.append(u.toLocalFile())
    return [p for p in paths if os.path.isfile(p)]


