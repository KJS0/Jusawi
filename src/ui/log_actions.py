from __future__ import annotations


def open_logs_folder(viewer) -> None:
    ok, err = viewer_open_logs_folder()
    try:
        if ok:
            viewer.statusBar().showMessage("로그 폴더를 열었습니다.", 2000)
        else:
            viewer.statusBar().showMessage(err or "로그 폴더를 열 수 없습니다.", 3000)
    except Exception:
        pass


def export_logs_zip(viewer) -> None:
    try:
        from PyQt6.QtWidgets import QFileDialog  # type: ignore[import]
        from ..utils.logging_setup import suggest_logs_zip_name
        default_name = suggest_logs_zip_name()
        dest, _ = QFileDialog.getSaveFileName(viewer, "로그 내보내기", default_name, "Zip Files (*.zip)")
    except Exception:
        dest = ""
    if not dest:
        return
    from ..utils.logging_setup import export_logs_zip as _export
    ok, err = _export(dest)
    try:
        if ok:
            viewer.statusBar().showMessage("로그를 내보냈습니다.", 2000)
        else:
            viewer.statusBar().showMessage(err or "로그 내보내기에 실패했습니다.", 3000)
    except Exception:
        pass


def viewer_open_logs_folder():
    from ..utils.logging_setup import open_logs_folder as _open
    return _open()


