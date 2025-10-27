import os
from PyQt6.QtGui import QAction


def rebuild_recent_menu(viewer) -> None:
    viewer.recent_menu.clear()
    # 존재하지 않는 항목 자동 정리 옵션 반영
    try:
        auto_prune = bool(getattr(viewer, "_recent_auto_prune_missing", True))
    except Exception:
        auto_prune = True
    # 최근 파일
    if getattr(viewer, "recent_files", None):
        from PyQt6.QtWidgets import QMenu  # type: ignore[import]
        files_menu = QMenu("최근 파일", viewer)
        for idx, item in enumerate(viewer.recent_files):
            path = item.get("path") if isinstance(item, dict) else str(item)
            if auto_prune and (not path or not os.path.isfile(path)):
                continue
            act = QAction(os.path.basename(path), viewer)
            act.setToolTip(path)
            act.triggered.connect(lambda _, p=path: viewer.load_image(p, source='recent'))
            files_menu.addAction(act)
        viewer.recent_menu.addMenu(files_menu)
    # 최근 폴더
    if getattr(viewer, "recent_folders", None):
        from PyQt6.QtWidgets import QMenu  # type: ignore[import]
        folders_menu = QMenu("최근 폴더", viewer)
        for item in viewer.recent_folders:
            dirp = item.get("path") if isinstance(item, dict) else str(item)
            if auto_prune and (not dirp or not os.path.isdir(dirp)):
                continue
            act = QAction(os.path.basename(dirp.rstrip("/\\")) or dirp, viewer)
            act.setToolTip(dirp)
            act.triggered.connect(lambda _, d=dirp: viewer._open_recent_folder(d))
            folders_menu.addAction(act)
        viewer.recent_menu.addMenu(folders_menu)
    if getattr(viewer, "recent_files", None) or getattr(viewer, "recent_folders", None):
        viewer.recent_menu.addSeparator()
    # 비우기 → 지우기
    clear_act = QAction("지우기", viewer)
    clear_act.triggered.connect(viewer.clear_recent)
    viewer.recent_menu.addAction(clear_act)

    # 최근 항목 없으면 비활성화
    has_any = bool(getattr(viewer, "recent_files", None) or getattr(viewer, "recent_folders", None))
    try:
        clear_act.setEnabled(has_any)
    except Exception:
        pass


def rebuild_log_menu(viewer) -> None:
    viewer.log_menu.clear()
    act_open = QAction("로그 폴더 열기", viewer)
    act_open.triggered.connect(viewer._open_logs_folder)
    viewer.log_menu.addAction(act_open)
    act_export = QAction("로그 내보내기(.zip)", viewer)
    act_export.triggered.connect(viewer._export_logs_zip)
    viewer.log_menu.addAction(act_export)

