import os
from PyQt6.QtCore import QObject, QEvent

from .dnd_handlers import urls_to_local_files


class DnDEventFilter(QObject):
    def __init__(self, viewer):
        super().__init__(viewer)
        self._viewer = viewer

    def eventFilter(self, obj, event):
        et = event.type()
        if et in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            md = getattr(event, 'mimeData', None)
            if md and event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
            return False
        if et == QEvent.Type.Drop:
            md = getattr(event, 'mimeData', None)
            if not (md and event.mimeData().hasUrls()):
                return False
            urls = event.mimeData().urls()
            paths = urls_to_local_files(urls)
            if not paths:
                return False
            files = [p for p in paths if os.path.isfile(p)]
            if files:
                self._viewer._handle_dropped_files(files)
            else:
                # 폴더 드롭은 비활성화
                self._viewer.statusBar().showMessage("이미지 파일만 드래그하여 열 수 있습니다.", 3000)
            event.acceptProposedAction()
            return True
        return False


