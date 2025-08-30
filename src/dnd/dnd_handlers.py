import os
from PyQt6.QtCore import QUrl

from ..utils.file_utils import SUPPORTED_FORMATS


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
        viewer.statusBar().showMessage("지원하는 이미지 파일이 없습니다.", 3000)
        return
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


