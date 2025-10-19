from __future__ import annotations

from ..dnd.dnd_handlers import handle_dropped_files as _handle_files  # type: ignore
from . import event_handlers as ev


def handle_dropped_files(owner, files):
    return _handle_files(owner, files)


def handle_dropped_folders(owner, folders):
    if not folders:
        owner.statusBar().showMessage("폴더가 없습니다.", 3000)
        return
    dir_path = folders[0]
    owner.scan_directory(dir_path)
    if 0 <= owner.current_image_index < len(owner.image_files_in_dir):
        owner.load_image(owner.image_files_in_dir[owner.current_image_index])
    else:
        owner.statusBar().showMessage("폴더에 표시할 이미지가 없습니다.", 3000)


def drag_enter(owner, event):
    ev.drag_enter(owner, event)


def drag_move(owner, event):
    ev.drag_move(owner, event)


def drop(owner, event):
    ev.drop(owner, event)


