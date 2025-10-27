import os
import tempfile
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
            # 로컬 파일/폴더/원격 URL 분리
            local_paths = urls_to_local_files(urls)
            files = []
            folders = []
            remote_urls = []
            for u in urls:
                try:
                    if u.isLocalFile():
                        p = u.toLocalFile()
                        if os.path.isfile(p):
                            files.append(p)
                        elif os.path.isdir(p):
                            folders.append(p)
                    else:
                        scheme = str(u.scheme()).lower()
                        if scheme in ("http", "https"):
                            remote_urls.append(str(u.toString()))
                except Exception:
                    pass
            # 폴더 드롭 처리(설정 필요)
            if folders:
                try:
                    if bool(getattr(self._viewer, "_drop_allow_folder", False)):
                        self._viewer._handle_dropped_folders(folders)
                        event.acceptProposedAction()
                        return True
                except Exception:
                    pass
                # 허용 안하면 메시지
                try:
                    self._viewer.statusBar().showMessage("설정에서 폴더 드롭을 허용하지 않았습니다.", 3000)
                except Exception:
                    pass
            # 원격 URL 자동 다운로드 기능 제거됨: 무시
            # 파일 처리
            if files:
                self._viewer._handle_dropped_files(files)
                event.acceptProposedAction()
                return True
            # 로컬 경로가 있으나 파일이 아닌 경우 안내
            try:
                self._viewer.statusBar().showMessage("이미지 파일만 드래그하여 열 수 있습니다.", 3000)
            except Exception:
                pass
            event.acceptProposedAction()
            return True
        return False


