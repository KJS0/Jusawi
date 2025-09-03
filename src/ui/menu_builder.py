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


def rebuild_log_menu(viewer) -> None:
    viewer.log_menu.clear()
    act_open = QAction("로그 폴더 열기", viewer)
    act_open.triggered.connect(viewer._open_logs_folder)
    viewer.log_menu.addAction(act_open)
    act_export = QAction("로그 내보내기(.zip)", viewer)
    act_export.triggered.connect(viewer._export_logs_zip)
    viewer.log_menu.addAction(act_export)

