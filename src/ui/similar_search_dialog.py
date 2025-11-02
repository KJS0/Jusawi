from __future__ import annotations

import os
from typing import List, Tuple

from PyQt6.QtWidgets import (  # type: ignore[import]
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal  # type: ignore[import]

from ..services.similarity_service import SimilarImageSearchService
from ..utils.logging_setup import get_logger


_log = get_logger("ui.SimilarSearchDialog")


class _SimilarWorker(QObject):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, svc: SimilarImageSearchService, query_image: str, files: List[str]):
        super().__init__()
        self._svc = svc
        self._q = query_image
        self._files = files

    def run(self):
        try:
            res = self._svc.search_similar(self._q, self._files, top_k=80, exclude_self=True)
            self.finished.emit(res)
        except Exception as e:
            self.failed.emit(str(e))


class SimilarSearchDialog(QDialog):
    def __init__(self, parent=None, files: List[str] | None = None, query_image: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("유사 사진 검색")
        self._files = [p for p in (files or []) if p and os.path.isfile(p)]
        self._query_image = str(query_image or "")
        self._thread: QThread | None = None
        self._worker: _SimilarWorker | None = None
        self._pix_cache: dict[str, object] = {}
        self._svc = SimilarImageSearchService()

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(6)
        except Exception:
            pass

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("실행")
        self.run_btn.clicked.connect(self._on_run)
        btn_row.addWidget(self.run_btn)
        btn_row.addStretch(1)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self.list_widget = QListWidget(self)
        try:
            from PyQt6.QtCore import QSize  # type: ignore[import]
            vm = QListWidget.ViewMode.IconMode
            icon_px = 192
            viewer = self.parent()
            try:
                if viewer is not None:
                    vm_str = str(getattr(viewer, "_search_result_view_mode", "grid"))
                    vm = QListWidget.ViewMode.IconMode if vm_str == "grid" else QListWidget.ViewMode.ListMode
                    icon_px = int(getattr(viewer, "_search_result_thumb_size", 192))
            except Exception:
                pass
            self.list_widget.setViewMode(vm)
            self.list_widget.setIconSize(QSize(icon_px, icon_px))
            self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
            self.list_widget.setMovement(QListWidget.Movement.Static)
            self.list_widget.setSpacing(10)
            self.list_widget.setStyleSheet(
                "QListWidget { background-color: #1F1F1F; color: #EAEAEA; border: 1px solid #333; }"
                " QListWidget::item { color: #EAEAEA; }"
                " QListWidget::item:selected { background-color: #2B2B2B; color: #FFFFFF; }"
            )
        except Exception:
            pass
        root.addWidget(self.list_widget, 1)

        try:
            from PyQt6.QtGui import QShortcut, QKeySequence  # type: ignore[import]
            sc = QShortcut(QKeySequence("Return"), self)
            sc.activated.connect(self._on_open_selected)
        except Exception:
            pass

        # 자동 실행: 쿼리 이미지와 파일이 준비된 경우
        try:
            if self._query_image and self._files:
                self._on_run()
        except Exception:
            pass

    def _on_run(self):
        if not (self._query_image and os.path.isfile(self._query_image)):
            QMessageBox.warning(self, "유사 검색", "현재 사진이 유효하지 않습니다.")
            return
        if not self._files:
            QMessageBox.information(self, "유사 검색", "검색할 파일이 없습니다.")
            return
        # 중복 실행 방지
        try:
            self.run_btn.setEnabled(False)
        except Exception:
            pass
        self.list_widget.clear()
        self._thread = QThread(self)
        self._worker = _SimilarWorker(self._svc, self._query_image, self._files)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_results)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _on_failed(self, msg: str):
        try:
            self.run_btn.setEnabled(True)
        except Exception:
            pass
        try:
            QMessageBox.warning(self, "유사 검색 실패", msg or "알 수 없는 오류")
        except Exception:
            pass

    def _on_results(self, results: List[Tuple[str, float]]):
        try:
            self.run_btn.setEnabled(True)
        except Exception:
            pass
        self._render_results(results)

    def _render_results(self, results: List[Tuple[str, float]]):
        self.list_widget.clear()

        try:
            from PyQt6.QtCore import QSize  # type: ignore[import]
            from PyQt6.QtGui import QPixmap, QIcon  # type: ignore[import]
        except Exception:
            QSize = None  # type: ignore
            QPixmap = None  # type: ignore
            QIcon = None  # type: ignore

        show_score = True
        icon_px = 192
        try:
            viewer = self.parent()
            if viewer is not None:
                icon_px = int(getattr(viewer, "_search_result_thumb_size", 192))
                show_score = bool(getattr(viewer, "_search_show_score", True))
        except Exception:
            pass

        def _load_icon(path: str, box: int):
            if path in self._pix_cache:
                return self._pix_cache[path]
            try:
                from PIL import Image  # type: ignore
            except Exception:
                return None
            if QPixmap is None or QIcon is None:
                return None
            try:
                with Image.open(path) as im:
                    im = im.convert("RGB")
                    im.thumbnail((box, box))
                    try:
                        import io
                        bio = io.BytesIO()
                        im.save(bio, format="PNG")
                        data = bio.getvalue()
                    except Exception:
                        return None
                pix = QPixmap()
                pix.loadFromData(data)
                icon = QIcon(pix)
                self._pix_cache[path] = icon
                return icon
            except Exception:
                return None

        for path, score in results:
            base = os.path.basename(path)
            # 0..1 범위 점수 표시 형식 고정
            if score < 0.0:
                score = 0.0
            if score > 1.0:
                score = 1.0
            label = f"{base}\n{score:.3f}" if show_score else base
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, path)
            icon = _load_icon(path, int(icon_px))
            try:
                if icon is not None:
                    item.setIcon(icon)
                    if QSize is not None:
                        item.setSizeHint(QSize(int(icon_px + 20), int(icon_px + (40 if show_score else 28))))
            except Exception:
                pass
            self.list_widget.addItem(item)

    def _on_open_selected(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        path = items[0].data(Qt.ItemDataRole.UserRole)
        try:
            viewer = self.parent()
            if viewer and hasattr(viewer, "load_image"):
                viewer.load_image(path, source='search')
                self.accept()
                return
        except Exception:
            pass
        QMessageBox.information(self, "열기", str(path))


