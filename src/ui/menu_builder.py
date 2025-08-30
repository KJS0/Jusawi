import os
from PyQt6.QtGui import QAction


def rebuild_recent_menu(viewer) -> None:
    viewer.recent_menu.clear()
    # 최근 파일만 표시
    if getattr(viewer, "recent_files", None):
        for item in viewer.recent_files:
            path = item.get("path") if isinstance(item, dict) else str(item)
            act = QAction(os.path.basename(path), viewer)
            act.setToolTip(path)
            act.triggered.connect(lambda _, p=path: viewer.load_image(p, source='recent'))
            viewer.recent_menu.addAction(act)
        viewer.recent_menu.addSeparator()
    # 비우기 → 지우기
    clear_act = QAction("지우기", viewer)
    clear_act.triggered.connect(viewer.clear_recent)
    viewer.recent_menu.addAction(clear_act)


