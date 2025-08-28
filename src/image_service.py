import os
from typing import Tuple, List
from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QImageReader, QTransform

from .file_utils import scan_directory_util


class _ImageWorker(QObject):
    done = pyqtSignal(str, QImage, bool, str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    def run(self):
        try:
            img, ok, err = _read_qimage_with_exif_auto_transform(self._path)
            if not ok:
                self.done.emit(self._path, QImage(), False, err)
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
        img, ok, err = _read_qimage_with_exif_auto_transform(path)
        if not ok:
            return path, None, False, err
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

    def save_with_transform(self,
                            img: QImage,
                            src_path: str,
                            dest_path: str,
                            rotation_degrees: int,
                            flip_horizontal: bool,
                            flip_vertical: bool,
                            quality: int = 95) -> tuple[bool, str]:
        """
        사용자 변환을 픽셀에 적용하여 저장. 저장 후 EXIF Orientation은 1로 간주(별도 설정 없음).
        """
        try:
            rot = _normalize_rotation(rotation_degrees)
            q = _sanitize_quality(quality)
            transformed = _apply_transform(img, rot, bool(flip_horizontal), bool(flip_vertical))
            return _save_qimage(transformed, dest_path, q)
        except Exception as e:
            return False, str(e)


def _read_qimage_with_exif_auto_transform(path: str) -> tuple[QImage, bool, str]:
    reader = QImageReader(path)
    # EXIF Orientation 등 자동 변환 활성화
    reader.setAutoTransform(True)
    img = reader.read()
    if img.isNull():
        return QImage(), False, reader.errorString() or "이미지를 불러올 수 없습니다."
    return img, True, ""


def _apply_transform(img: QImage, rotation_degrees: int, flip_h: bool, flip_v: bool) -> QImage:
    try:
        t = QTransform()
        rot = int(rotation_degrees) % 360
        if rot:
            t.rotate(rot)
        sx = -1.0 if flip_h else 1.0
        sy = -1.0 if flip_v else 1.0
        if sx != 1.0 or sy != 1.0:
            t.scale(sx, sy)
        # Smooth for quality; QImage handles bounds expansion automatically
        return img.transformed(t, Qt.TransformationMode.SmoothTransformation)
    except Exception:
        return img


def _guess_format_from_path(path: str) -> str:
    try:
        ext = os.path.splitext(path)[1].lower().lstrip('.')
        if ext == 'jpg':
            return 'JPEG'
        if ext == 'tif':
            return 'TIFF'
        if ext:
            return ext.upper()
    except Exception:
        pass
    return ''


def _save_qimage(img: QImage, dest_path: str, quality: int) -> tuple[bool, str]:
    fmt = _guess_format_from_path(dest_path)
    try:
        # 품질은 JPEG 등에 적용. 포맷 추정 실패 시 Qt가 확장자로 추정
        ok = img.save(dest_path, fmt if fmt else None, quality)
        if not ok:
            return False, "이미지를 저장할 수 없습니다."
        return True, ""
    except Exception as e:
        return False, str(e)


def _normalize_rotation(rot: int) -> int:
    rot = int(rot) % 360
    if rot % 90 != 0:
        rot = (round(rot / 90.0) * 90) % 360
    return rot


def _sanitize_quality(q: int) -> int:
    try:
        qi = int(q)
        return 1 if qi < 1 else (100 if qi > 100 else qi)
    except Exception:
        return 95
