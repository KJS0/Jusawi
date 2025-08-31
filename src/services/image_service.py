import os
from typing import Tuple, List, Callable, Optional, Any
from collections import OrderedDict
from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt, QRunnable, QThreadPool
from PyQt6.QtGui import QImage, QImageReader, QTransform

from ..utils.file_utils import scan_directory_util, safe_write_bytes
from .metadata_service import extract_metadata, encode_with_metadata


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
        # 간단한 LRU QImage 캐시 (용량 제한: 바이트 단위)
        self._img_cache = _QImageCache(max_bytes=256 * 1024 * 1024)  # 기본 256MB
        # 프리로드용 스레드풀 및 세대 토큰
        self._pool = QThreadPool.globalInstance()
        self._preload_generation = 0

    def scan_directory(self, dir_path: str, current_image_path: str | None):
        return scan_directory_util(dir_path, current_image_path)

    def load(self, path: str) -> Tuple[str, QImage | None, bool, str]:
        # 캐시 히트 시 즉시 반환
        cached = self._img_cache.get(path)
        if cached is not None and not cached.isNull():
            return path, cached, True, ""
        img, ok, err = _read_qimage_with_exif_auto_transform(path)
        if not ok:
            return path, None, False, err
        self._img_cache.put(path, img)
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

    # --- 프리로드/캐시 API ---
    def get_cached_image(self, path: str) -> Optional[QImage]:
        return self._img_cache.get(path)

    def invalidate_path(self, path: str) -> None:
        self._img_cache.delete(path)

    def preload(self, paths: List[str], priority: int = 0) -> None:
        """경로 목록을 백그라운드에서 디코드하여 이미지 캐시에 저장.
        취소는 세대 카운터 증가로 구현(새 호출 시 이전 작업은 효과적으로 무시됨).
        """
        if not paths:
            return
        # 세대 증가: 기존 작업은 결과가 와도 화면에 영향 없음. 캐시에 들어가도 용량 제한으로 관리됨.
        self._preload_generation += 1
        generation = self._preload_generation

        # 중복/이미 캐시된 항목은 제외
        unique: List[str] = []
        seen: set[str] = set()
        for p in paths:
            if p and p not in seen and self._img_cache.get(p) is None:
                seen.add(p)
                unique.append(p)
        if not unique:
            return

        for p in unique:
            task = _PreloadTask(path=p, generation=generation, done=self._on_preload_done)
            # 낮은 우선순위 힌트를 주기 위해 start() 대신 start with priority 사용 (Qt는 힌트로 취급)
            try:
                self._pool.start(task, priority)
            except Exception:
                # 예외는 무시 (풀 포화 등)
                pass

    def _on_preload_done(self, path: str, img: QImage, success: bool, error: str, generation: int) -> None:
        # 최신 세대가 아니어도 캐시에 넣는 것은 허용(다음에 히트될 수 있음)
        if success and not img.isNull():
            self._img_cache.put(path, img)
        # 실패는 무시 (로그 없음)

    def save_with_transform(self,
                            img: QImage,
                            src_path: str,
                            dest_path: str,
                            rotation_degrees: int,
                            flip_horizontal: bool,
                            flip_vertical: bool,
                            quality: int = 95) -> tuple[bool, str]:
        """
        안전 저장 + 메타데이터 보존.
        - 픽셀에 변환 적용 후 Orientation=1로 정규화된 EXIF과 ICC/XMP 가능하면 유지
        - 임시 파일에 기록 후 원자 교체(Windows: ReplaceFileW)
        """
        try:
            rot = _normalize_rotation(rotation_degrees)
            q = _sanitize_quality(quality)
            transformed = _apply_transform(img, rot, bool(flip_horizontal), bool(flip_vertical))

            # Pillow로 인코딩하기 위해 QImage -> bytes (RGBA) 추출 후 PIL 로딩
            from PIL import Image as PILImage  # type: ignore
            import io

            fmt = _guess_format_from_path(dest_path)
            if not fmt:
                fmt = 'JPEG'
            # QImage를 RGBA 바이트로 변환
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

            # 메타데이터 추출/정규화
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


class _QImageCache:
    """바이트 상한 기반 간단 LRU 캐시(QImage)."""

    def __init__(self, max_bytes: int = 256 * 1024 * 1024):
        self._max_bytes = int(max_bytes)
        self._store: "OrderedDict[str, QImage]" = OrderedDict()
        self._bytes_used = 0

    def _estimate_bytes(self, img: QImage) -> int:
        try:
            return int(img.sizeInBytes())
        except Exception:
            # 폴백 추정
            bpp = max(1, int(img.depth() / 8))
            return img.width() * img.height() * bpp

    def get(self, key: str) -> Optional[QImage]:
        try:
            img = self._store.pop(key)
        except KeyError:
            return None
        # 최근 사용으로 이동
        self._store[key] = img
        return img

    def put(self, key: str, img: QImage) -> None:
        if not key:
            return
        # 기존 항목 제거
        if key in self._store:
            try:
                old = self._store.pop(key)
                self._bytes_used -= self._estimate_bytes(old)
            except Exception:
                pass
        self._store[key] = img
        self._bytes_used += self._estimate_bytes(img)
        self._evict_if_needed()

    def delete(self, key: str) -> None:
        if key in self._store:
            try:
                img = self._store.pop(key)
                self._bytes_used -= self._estimate_bytes(img)
            except Exception:
                pass

    def clear(self) -> None:
        self._store.clear()
        self._bytes_used = 0

    def _evict_if_needed(self) -> None:
        while self._bytes_used > self._max_bytes and self._store:
            k, v = self._store.popitem(last=False)  # LRU 제거
            try:
                self._bytes_used -= self._estimate_bytes(v)
            except Exception:
                pass


class _PreloadTask(QRunnable):
    """경량 프리로드 작업: QImage를 디코드해 콜백으로 전달."""

    def __init__(self, path: str, generation: int, done: Callable[[str, QImage, bool, str, int], None]):
        super().__init__()
        self._path = path
        self._generation = generation
        self._done = done

    def run(self) -> None:
        try:
            img, ok, err = _read_qimage_with_exif_auto_transform(self._path)
            if not ok:
                self._done(self._path, QImage(), False, err, self._generation)
                return
            self._done(self._path, img, True, "", self._generation)
        except Exception as e:
            self._done(self._path, QImage(), False, str(e), self._generation)
