import os
from typing import Tuple, List
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QImage

from .file_utils import scan_directory_util


class _ImageWorker(QObject):
    done = pyqtSignal(str, QImage, bool, str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    def run(self):
        try:
            img = QImage(self._path)
            if img.isNull():
                self.done.emit(self._path, QImage(), False, "이미지를 불러올 수 없습니다.")
                return
            self.done.emit(self._path, img, True, "")
        except Exception as e:
            self.done.emit(self._path, QImage(), False, str(e))


class ImageService(QObject):
    loaded = pyqtSignal(str, QImage, bool, str)  # path, img, success, error

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _ImageWorker | None = None

    def scan_directory(self, dir_path: str, current_image_path: str | None):
        return scan_directory_util(dir_path, current_image_path)

    def load(self, path: str) -> Tuple[str, QImage | None, bool, str]:
        img = QImage(path)
        if img.isNull():
            return path, None, False, "이미지를 불러올 수 없습니다."
        return path, img, True, ""

    def load_async(self, path: str) -> None:
        # 이전 작업 취소/정리
        if self._thread:
            try:
                self._thread.quit()
                # 충분히 대기하여 안전 종료 유도
                self._thread.wait(2000)
            except Exception:
                pass
            finally:
                # 남아있으면 강제 종료 (최후 수단)
                try:
                    if self._thread.isRunning():
                        self._thread.terminate()
                        self._thread.wait(1000)
                except Exception:
                    pass
                self._cleanup_thread()

        self._thread = QThread()
        self._worker = _ImageWorker(path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_worker_done)
        self._worker.done.connect(lambda *_: self._thread.quit())
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _on_worker_done(self, path: str, img: QImage, success: bool, error: str):
        self.loaded.emit(path, img, success, error)

    def _on_thread_finished(self):
        self._cleanup_thread()

    def _cleanup_thread(self):
        try:
            if self._worker is not None:
                self._worker.deleteLater()
        except Exception:
            pass
        try:
            if self._thread is not None:
                self._thread.deleteLater()
        except Exception:
            pass
        self._worker = None
        self._thread = None

    def shutdown(self):
        # 서비스 종료 시 안전하게 스레드 중지
        if self._thread:
            try:
                self._thread.quit()
                self._thread.wait(2000)
            except Exception:
                pass
            finally:
                try:
                    if self._thread.isRunning():
                        self._thread.terminate()
                        self._thread.wait(1000)
                except Exception:
                    pass
                self._cleanup_thread()


