from __future__ import annotations

import os
from typing import List, Tuple
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QProgressDialog  # type: ignore[import]
from PyQt6.QtGui import QIcon, QPixmap  # type: ignore[import]
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer  # type: ignore[import]

try:
    from PIL import Image, ImageQt  # type: ignore
except Exception:
    Image = None  # type: ignore
    ImageQt = None  # type: ignore

from ..services.similarity_service import SimilarityIndex


class _Worker(QThread):
    progress = pyqtSignal(int, str)
    done = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, anchor: str, folder: str, svc: SimilarityIndex, top_k: int = 100):
        super().__init__()
        self._anchor = anchor
        self._folder = folder
        self._svc = svc
        self._top_k = top_k
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            self.progress.emit(10, "폴더 인덱싱…")
            # 인덱싱 단계: 내부에서 캐시/스캔 처리
            if self._cancel:
                self.failed.emit("취소됨")
                return
            self._svc.build_or_load(self._folder)
            self.progress.emit(60, "유사도 계산…")
            if self._cancel:
                self.failed.emit("취소됨")
                return
            # auto: 대용량 폴더는 ANN, 그 외에는 pHash→CLIP
            res = self._svc.similar_auto(self._anchor, self._folder, top_k=self._top_k, mode="auto")
            self.progress.emit(100, "완료")
            self.done.emit(res)
        except Exception as e:
            self.failed.emit(str(e))


class SimilarSearchDialog(QDialog):
    def __init__(self, parent, anchor_path: str, folder: str):
        super().__init__(parent)
        self.setWindowTitle("유사 사진 찾기")
        self._anchor = anchor_path
        self._folder = folder
        self._svc = SimilarityIndex()
        self._worker: _Worker | None = None
        self._progress: QProgressDialog | None = None

        lay = QVBoxLayout(self)
        self.listw = QListWidget(self)
        try:
            # 탐색기 스타일 썸네일 그리드 구성 (4열 x 3행, 총 12개 초기 표시)
            cols, rows = 4, 3
            icon = QSize(160, 160)
            # 텍스트 두 줄(+여유)을 위한 그리드 높이 확장
            grid = QSize(190, 230)
            spacing = 6
            border = 16  # 여유 마진
            width = cols * grid.width() + (cols - 1) * spacing + border
            height = rows * grid.height() + (rows - 1) * spacing + border

            self.listw.setViewMode(self.listw.ViewMode.IconMode)
            self.listw.setIconSize(icon)
            self.listw.setResizeMode(self.listw.ResizeMode.Adjust)
            self.listw.setMovement(self.listw.Movement.Static)
            self.listw.setUniformItemSizes(True)
            self.listw.setWrapping(True)
            self.listw.setGridSize(grid)
            try:
                # 너무 긴 파일명은 가운데 생략으로 표시
                self.listw.setTextElideMode(Qt.TextElideMode.ElideMiddle)
            except Exception:
                pass
            self.listw.setSpacing(spacing)
            # 4열 강제: 리스트 너비를 그리드 폭에 맞춰 고정
            self.listw.setMinimumWidth(width)
            self.listw.setMaximumWidth(width)
            self.listw.setMinimumHeight(height)
            self.listw.setMaximumHeight(height)
        except Exception:
            pass
        lay.addWidget(self.listw, 1)
        self.listw.itemDoubleClicked.connect(self._on_open)

        self._pending: list[tuple[str, float]] = []
        self._batch_size = 12
        self._start_search()

    def _start_search(self):
        self.listw.clear()
        # 진행/취소 가능한 로딩창
        self._progress = QProgressDialog("유사 사진 검색 준비 중…", "취소", 0, 100, self)
        try:
            self._progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            self._progress.setMinimumDuration(0)
            self._progress.setAutoClose(True)
            self._progress.setAutoReset(True)
            self._progress.setValue(0)
            self._progress.show()
        except Exception:
            pass
        self._progress.canceled.connect(self._on_cancel)
        # 워커 스레드 시작
        self._worker = _Worker(self._anchor, self._folder, self._svc, top_k=12)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, val: int, msg: str):
        try:
            if self._progress:
                self._progress.setValue(int(val))
                self._progress.setLabelText(msg)
        except Exception:
            pass

    def _on_done(self, res: List[Tuple[str, float]]):
        try:
            if self._progress:
                self._progress.close()
        except Exception:
            pass
        self._progress = None
        self._worker = None
        # 배치로 추가해 UI 끊김 완화
        self._pending = list(res)
        self._drain_batch()

    def _drain_batch(self):
        if not self._pending:
            return
        chunk = self._pending[:self._batch_size]
        self._pending = self._pending[self._batch_size:]
        # grid와 아이콘/텍스트 레이아웃 파라미터는 초기 구성과 동일하게 사용
        grid_size = QSize(190, 230)
        for path, score in chunk:
            it = QListWidgetItem(f"{os.path.basename(path)}  ({score:.3f})")
            pm = QPixmap(path)
            if pm.isNull() and Image is not None and ImageQt is not None:
                try:
                    with Image.open(path) as im:
                        im.thumbnail((160,160))
                        pm = QPixmap.fromImage(ImageQt.ImageQt(im))  # type: ignore
                except Exception:
                    pass
            if not pm.isNull():
                it.setIcon(QIcon(pm))
            try:
                it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
                it.setSizeHint(grid_size)
            except Exception:
                pass
            it.setData(Qt.ItemDataRole.UserRole, path)
            self.listw.addItem(it)
        if self._pending:
            QTimer.singleShot(0, self._drain_batch)

    def _on_failed(self, err: str):
        try:
            if self._progress:
                self._progress.close()
        except Exception:
            pass
        self._progress = None
        self._worker = None
        try:
            self.listw.clear()
            self.listw.addItem(QListWidgetItem(f"검색 실패: {err}"))
        except Exception:
            pass

    def _on_cancel(self):
        try:
            if self._worker:
                self._worker.cancel()
        except Exception:
            pass

    def _on_open(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        try:
            self.parent().load_image(path, source='similar')
            self.accept()
        except Exception:
            pass


