from __future__ import annotations

import os
from typing import List, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QListWidget, QListWidgetItem, QMessageBox, QProgressDialog
)  # type: ignore[import]
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal  # type: ignore[import]

from ..services.online_search_service import OnlineEmbeddingIndex
from ..utils.logging_setup import get_logger

_log = get_logger("ui.NaturalSearchDialog")


class _SearchWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, index: OnlineEmbeddingIndex, files: List[str], query: str, verify_mode: str, verify_top_n: int):
        super().__init__()
        self._index = index
        self._files = files
        self._query = query
        self._vmode = verify_mode
        self._vtop = int(max(0, verify_top_n))

    def run(self):
        try:
            res = self._index.search(
                image_paths=self._files,
                query_text=self._query,
                top_k=int(os.getenv("SEARCH_TOP_K", "80") or 80),
                verify_top_n=self._vtop if self._vtop > 0 else int(os.getenv("SEARCH_VERIFY_TOP_N", "20") or 20),
                verify_mode=(self._vmode or os.getenv("SEARCH_VERIFY_MODE", "normal") or "normal"),
                progress_cb=lambda p, m: self.progress.emit(int(p), str(m)),
            )
            self.finished.emit(res)
        except Exception as e:
            self.failed.emit(str(e))


class NaturalSearchDialog(QDialog):
    def __init__(self, parent=None, files: List[str] | None = None, initial_query: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("자연어 검색")
        self._files = files or []
        self._index = OnlineEmbeddingIndex()
        self._thread: QThread | None = None
        self._worker: _SearchWorker | None = None

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(6)
        except Exception:
            pass

        self.query_edit = QTextEdit(self)
        try:
            self.query_edit.setPlaceholderText("예) 해질녘 해변에서 역광으로 산책하는 사람")
        except Exception:
            pass
        root.addWidget(QLabel("질의"))
        root.addWidget(self.query_edit)
        try:
            if initial_query:
                self.query_edit.setPlainText(str(initial_query))
        except Exception:
            pass

        btn_row = QHBoxLayout()
        self.search_btn = QPushButton("검색")
        self.search_btn.clicked.connect(self._on_search)
        btn_row.addWidget(self.search_btn)
        # 재검증 모드/상위 N
        from PyQt6.QtWidgets import QComboBox, QSpinBox  # type: ignore[import]
        self.combo_verify_mode = QComboBox(self)
        self.combo_verify_mode.addItems(["엄격", "보통", "느슨함"])  # strict/normal/loose
        self.spin_verify_topn = QSpinBox(self); self.spin_verify_topn.setRange(0, 500); self.spin_verify_topn.setValue(20)
        btn_row.addWidget(QLabel("재검증"))
        btn_row.addWidget(self.combo_verify_mode)
        btn_row.addWidget(QLabel("상위 N"))
        btn_row.addWidget(self.spin_verify_topn)
        btn_row.addStretch(1)
        self.open_btn = QPushButton("선택 열기")
        self.open_btn.clicked.connect(self._on_open_selected)
        btn_row.addWidget(self.open_btn)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self.list_widget = QListWidget(self)
        try:
            # 아이콘 보기로 전환, 큰 썸네일
            from PyQt6.QtGui import QIcon, QPixmap  # type: ignore[import]
            from PyQt6.QtCore import QSize  # type: ignore[import]
            self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
            self.list_widget.setIconSize(QSize(192, 192))
            self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
            self.list_widget.setMovement(QListWidget.Movement.Static)
            self.list_widget.setSpacing(10)
        except Exception:
            pass
        root.addWidget(self.list_widget, 1)

        self._progress = QProgressDialog("검색 준비 중...", "중지", 0, 100, self)
        try:
            self._progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            self._progress.reset()
            self._progress.hide()
        except Exception:
            pass
        # 기본값: 부모 뷰어 설정 반영
        try:
            viewer = self.parent()
            if viewer is not None:
                vm = str(getattr(viewer, "_search_verify_mode_default", "strict"))
                self.combo_verify_mode.setCurrentIndex({"strict":0,"normal":1,"loose":2}.get(vm,0))  # type: ignore[attr-defined]
                self.spin_verify_topn.setValue(int(getattr(viewer, "_search_verify_topn_default", 20)))  # type: ignore[attr-defined]
        except Exception:
            pass

    def _on_search(self):
        q = (self.query_edit.toPlainText() or "").strip()
        if not q:
            QMessageBox.information(self, "자연어 검색", "질의를 입력하세요.")
            return
        if not self._files:
            QMessageBox.information(self, "자연어 검색", "현재 폴더에 이미지가 없습니다.")
            return
        if self._thread is not None:
            return
        self._progress.setValue(0)
        self._progress.setLabelText("검색 시작")
        self._progress.show()

        # 모드/상위 N 읽기
        try:
            mi = int(self.combo_verify_mode.currentIndex())
        except Exception:
            mi = 1
        mode = "strict" if mi == 0 else ("loose" if mi == 2 else "normal")
        try:
            topn = int(self.spin_verify_topn.value())
        except Exception:
            topn = 20

        self._thread = QThread(self)
        self._worker = _SearchWorker(self._index, self._files, q, mode, topn)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _on_progress(self, p: int, msg: str):
        try:
            self._progress.setValue(int(max(0, min(100, p))))
            if msg:
                self._progress.setLabelText(str(msg))
        except Exception:
            pass

    def _on_finished(self, results: List[Tuple[str, float]]):
        self._cleanup_worker()
        try:
            self._progress.hide()
        except Exception:
            pass
        self._render_results(results)

    def _on_failed(self, err: str):
        self._cleanup_worker()
        try:
            self._progress.hide()
        except Exception:
            pass
        QMessageBox.warning(self, "자연어 검색", f"실패: {err}")

    def _cleanup_worker(self):
        try:
            if self._worker:
                self._worker.deleteLater()
        except Exception:
            pass
        try:
            if self._thread:
                self._thread.quit()
                self._thread.wait(1000)
                self._thread.deleteLater()
        except Exception:
            pass
        self._thread = None
        self._worker = None

    def _render_results(self, results: List[Tuple[str, float]]):
        self.list_widget.clear()
        try:
            from PyQt6.QtGui import QIcon, QPixmap  # type: ignore[import]
            from PyQt6.QtCore import QSize  # type: ignore[import]
        except Exception:
            QIcon = None  # type: ignore
            QPixmap = None  # type: ignore
            QSize = None  # type: ignore
        for path, score in results:
            base = os.path.basename(path)
            label = f"{base}\n{score:.3f}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, path)
            # 썸네일 생성 시도
            icon = None
            try:
                if QPixmap is not None:
                    px = QPixmap(path)
                    if not px.isNull():
                        # 가로세로 192 박스에 맞추어 부드럽게 스케일
                        box = 192
                        px = px.scaled(box, box, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        icon = QIcon(px)
            except Exception:
                pass
            try:
                if icon is not None:
                    item.setIcon(icon)
                    if QSize is not None:
                        item.setSizeHint(QSize(212, 232))
            except Exception:
                pass
            self.list_widget.addItem(item)

    def _on_open_selected(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        path = items[0].data(Qt.ItemDataRole.UserRole)
        try:
            # 부모 뷰어가 있으면 열기 시도
            viewer = self.parent()
            if viewer and hasattr(viewer, "load_image"):
                viewer.load_image(path, source='search')
                self.accept()
                return
        except Exception:
            pass
        # 폴백: 경로만 알림
        QMessageBox.information(self, "열기", str(path))