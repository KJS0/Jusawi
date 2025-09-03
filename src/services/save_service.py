import os
from typing import Callable
from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt  # type: ignore[import]
from PyQt6.QtGui import QImage, QTransform, QColorSpace  # type: ignore[import]

from ..utils.file_utils import safe_write_bytes
from .metadata_service import extract_metadata, encode_with_metadata
from ..utils.logging_setup import get_logger

_log = get_logger("svc.SaveService")


class _CancellationToken(QObject):
    def __init__(self):
        super().__init__()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled


class _SaveWorker(QObject):
    progress = pyqtSignal(int)
    done = pyqtSignal(bool, str)

    def __init__(self, img: QImage, src_path: str, dest_path: str, rotation_degrees: int,
                 flip_horizontal: bool, flip_vertical: bool, quality: int, token: _CancellationToken):
        super().__init__()
        self._img = img
        self._src = src_path
        self._dst = dest_path
        self._rot = rotation_degrees
        self._fh = flip_horizontal
        self._fv = flip_vertical
        self._q = quality
        self._token = token

    def run(self):
        try:
            if self._token.is_cancelled():
                self.done.emit(False, "작업이 취소되었습니다.")
                return
            self.progress.emit(10)
            rot = _normalize_rotation(self._rot)
            q = _sanitize_quality(self._q)
            transformed = _apply_transform(self._img, rot, bool(self._fh), bool(self._fv))

            if self._token.is_cancelled():
                self.done.emit(False, "작업이 취소되었습니다.")
                return
            self.progress.emit(30)

            from PIL import Image as PILImage  # type: ignore
            fmt = _guess_format_from_path(self._dst) or 'JPEG'
            qt_format = QImage.Format.Format_RGBA8888
            converted = transformed if transformed.format() == qt_format else transformed.convertToFormat(qt_format)
            width = converted.width()
            height = converted.height()
            ptr = converted.bits()
            ptr.setsize(converted.sizeInBytes())
            raw = bytes(ptr)
            pil_image = PILImage.frombytes('RGBA', (width, height), raw)
            if fmt.upper() == 'JPEG':
                pil_image = pil_image.convert('RGB')

            if self._token.is_cancelled():
                self.done.emit(False, "작업이 취소되었습니다.")
                return
            self.progress.emit(60)

            meta = extract_metadata(self._src)
            ok, encoded_bytes, err = encode_with_metadata(pil_image, fmt, q, meta)
            if not ok:
                self.done.emit(False, err or "인코딩 실패")
                return

            if self._token.is_cancelled():
                self.done.emit(False, "작업이 취소되었습니다.")
                return
            self.progress.emit(85)

            ok2, err2 = safe_write_bytes(self._dst, encoded_bytes, write_through=True, retries=6)
            if not ok2:
                self.done.emit(False, err2 or "원자적 저장 실패")
                return
            self.progress.emit(100)
            self.done.emit(True, "")
        except Exception as e:
            self.done.emit(False, str(e))
        finally:
            try:
                _ok = 'e' not in locals()
                _log.info("save_worker_done | dst=%s | ok=%s", os.path.basename(self._dst), _ok)
            except Exception:
                pass


class SaveService:
    def __init__(self) -> None:
        self._save_thread: QThread | None = None
        self._save_worker: _SaveWorker | None = None
        self._save_token: _CancellationToken | None = None

    def save_async(self,
                   img: QImage,
                   src_path: str,
                   dest_path: str,
                   rotation_degrees: int,
                   flip_horizontal: bool,
                   flip_vertical: bool,
                   quality: int,
                   on_progress: Callable[[int], None] | None,
                   on_done: Callable[[bool, str], None] | None) -> None:
        try:
            self.cancel_save()
        except Exception:
            pass
        token = _CancellationToken()
        worker = _SaveWorker(img, src_path, dest_path, rotation_degrees, flip_horizontal, flip_vertical, quality, token)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def _cleanup():
            try:
                thread.quit()
                thread.wait(2000)
            except Exception:
                pass
            try:
                worker.deleteLater()
            except Exception:
                pass
            try:
                thread.deleteLater()
            except Exception:
                pass
            self._save_worker = None
            self._save_thread = None
            self._save_token = None

        worker.progress.connect(lambda p: on_progress(p) if callable(on_progress) else None)
        worker.done.connect(lambda ok, err: (on_done(ok, err) if callable(on_done) else None))
        worker.done.connect(_cleanup)
        thread.start()
        self._save_worker = worker
        self._save_thread = thread
        self._save_token = token

    def cancel_save(self) -> None:
        try:
            if self._save_token:
                self._save_token.cancel()
        except Exception:
            pass
        try:
            if self._save_thread and self._save_thread.isRunning():
                self._save_thread.requestInterruption()
        except Exception:
            pass

    def save_with_transform(self,
                             img: QImage,
                             src_path: str,
                             dest_path: str,
                             rotation_degrees: int,
                             flip_horizontal: bool,
                             flip_vertical: bool,
                             quality: int = 95) -> tuple[bool, str]:
        try:
            rot = _normalize_rotation(rotation_degrees)
            q = _sanitize_quality(quality)
            transformed = _apply_transform(img, rot, bool(flip_horizontal), bool(flip_vertical))

            from PIL import Image as PILImage  # type: ignore

            fmt = _guess_format_from_path(dest_path)
            if not fmt:
                fmt = 'JPEG'
            qt_format = QImage.Format.Format_RGBA8888
            if transformed.format() != qt_format:
                converted = transformed.convertToFormat(qt_format)
            else:
                converted = transformed
            width = converted.width()
            height = converted.height()
            ptr = converted.bits()
            ptr.setsize(converted.sizeInBytes())
            raw = bytes(ptr)
            pil_image = PILImage.frombytes('RGBA', (width, height), raw)
            if fmt.upper() == 'JPEG':
                pil_image = pil_image.convert('RGB')

            meta = extract_metadata(src_path)
            ok, encoded_bytes, err = encode_with_metadata(pil_image, fmt, q, meta)
            if not ok:
                return False, err or "인코딩 실패"

            ok2, err2 = safe_write_bytes(dest_path, encoded_bytes, write_through=True, retries=6)
            if not ok2:
                return False, err2 or "원자적 저장 실패"
            return True, ""
        except Exception as e:
            return False, str(e)


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


