from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import JusawiViewer


def drag_enter(viewer: "JusawiViewer", event) -> None:
    if event.mimeData().hasUrls():
        event.acceptProposedAction()
    else:
        event.ignore()


def drag_move(viewer: "JusawiViewer", event) -> None:
    if event.mimeData().hasUrls():
        event.acceptProposedAction()
    else:
        event.ignore()


def drop(viewer: "JusawiViewer", event) -> None:
    urls = event.mimeData().urls()
    if not urls:
        event.ignore()
        return
    from ..dnd.dnd_handlers import urls_to_local_files
    import os
    paths = urls_to_local_files(urls)
    if not paths:
        event.ignore()
        return
    files = [p for p in paths if os.path.isfile(p)]
    if files:
        viewer._handle_dropped_files(files)
    event.acceptProposedAction()


def resize(viewer: "JusawiViewer", event) -> None:
    # QGraphicsView가 자체 맞춤을 처리하므로 특별 동작 없음
    # 필요 시 추후 앵커/뷰 모드에 따른 재적용을 여기서 수행
    return


