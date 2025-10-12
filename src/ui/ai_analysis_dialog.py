from __future__ import annotations

import os
from typing import Any, Dict

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QWidget, QTabWidget, QMessageBox, QProgressDialog
)  # type: ignore[import]
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal  # type: ignore[import]

from ..services.ai_analysis_service import AIAnalysisService, AnalysisContext
from ..utils.logging_setup import get_logger

_log = get_logger("ui.AIAnalysisDialog")


class _AnalysisWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict, str)
    failed = pyqtSignal(str)

    def __init__(self, service: AIAnalysisService, image_path: str, ctx: AnalysisContext, is_cancelled_callable):
        super().__init__()
        self._service = service
        self._image_path = image_path
        self._ctx = ctx
        self._cancel = is_cancelled_callable

    def run(self):
        try:
            data = self._service.analyze(
                self._image_path,
                context=self._ctx,
                progress_cb=lambda p, m: self.progress.emit(int(p), str(m)),
                is_cancelled=lambda: bool(self._cancel()),
            )
            # 취소 시에도 일관되게 finished로 넘겨 UI가 정리되도록 함
            self.finished.emit(data, "ok")
        except Exception as e:
            self.failed.emit(str(e))


class AIAnalysisDialog(QDialog):
    def __init__(self, parent=None, image_path: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("AI 분석")
        self._image_path = image_path or ""
        self._service = AIAnalysisService()
        self._data: Dict[str, Any] = {}
        self._thread: QThread | None = None
        self._worker: _AnalysisWorker | None = None
        self._cancel_flag = False

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(6)
        except Exception:
            pass

        title = QLabel(os.path.basename(self._image_path) if self._image_path else "-")
        try:
            title.setStyleSheet("font-weight: bold; font-size: 14px; color: #EAEAEA;")
        except Exception:
            pass
        sub = QLabel(self._image_path)
        try:
            sub.setStyleSheet("color: #BEBEBE;")
        except Exception:
            pass
        root.addWidget(title)
        root.addWidget(sub)

        # 캡션/태그만 표시
        self.captions_view = QTextEdit(self)
        try:
            self.captions_view.setReadOnly(True)
        except Exception:
            pass
        root.addWidget(self.captions_view, 1)

        # Buttons
        btn_row = QHBoxLayout()
        self.analyze_btn = QPushButton("분석 실행")
        self.analyze_btn.clicked.connect(self._on_analyze)
        btn_row.addWidget(self.analyze_btn)

        btn_row.addStretch(1)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self._on_close)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        # 진행률/취소 가능한 로딩창 준비(필요 시 표시)
        self._progress = QProgressDialog("AI 분석 준비 중...", "중지", 0, 100, self)
        try:
            self._progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            self._progress.canceled.connect(self._on_cancel)
            self._progress.reset()
            self._progress.hide()
        except Exception:
            pass

        if self._image_path:
            try:
                self._on_analyze()
            except Exception:
                pass

    def _on_cancel(self):
        self._cancel_flag = True
        try:
            self._progress.setLabelText("취소 중...")
        except Exception:
            pass

    def _is_cancelled(self) -> bool:
        return bool(self._cancel_flag)

    def _on_analyze(self):
        if not self._image_path or not os.path.exists(self._image_path):
            QMessageBox.warning(self, "AI 분석", "유효한 파일이 없습니다.")
            return
        if self._thread is not None:
            return
        self._cancel_flag = False
        self._progress.setValue(0)
        self._progress.setLabelText("분석 시작")
        self._progress.show()

        self._thread = QThread(self)
        self._worker = _AnalysisWorker(self._service, self._image_path, AnalysisContext(), self._is_cancelled)
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

    def _on_finished(self, data: Dict[str, Any], status: str):
        self._cleanup_worker()
        self._data = data or {}
        self._render(data or {})
        try:
            self._progress.hide()
        except Exception:
            pass

    def _on_failed(self, err: str):
        self._cleanup_worker()
        try:
            self._progress.hide()
        except Exception:
            pass
        QMessageBox.warning(self, "AI 분석", f"분석 실패: {err}")

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

    def _render(self, data: Dict[str, Any]):
        # 사용자가 원한 단순 표기: 짧은 캡션, 긴 캡션, 태그, 주제만
        sc = str(data.get("short_caption") or "").strip()
        lc = str(data.get("long_caption") or "").strip()
        tags = data.get("tags") or []
        subj = data.get("subjects") or []
        lines: list[str] = []
        if sc:
            lines.append(f"짧은 캡션 : {sc}")
        if lc:
            lines.append(f"긴 캡션 : {lc}")
        if tags:
            lines.append("태그 : " + ", ".join([str(t) for t in tags]))
        if subj:
            lines.append("주제 : " + ", ".join([str(s) for s in subj]))
        self.captions_view.setPlainText("\n".join(lines))

        # JSON 보기/저장은 제거됨

    def _on_close(self):
        if self._thread is not None:
            # 로딩창을 끄면 로딩 중단: 취소 플래그를 올리고 워커 정리
            self._on_cancel()
            self._cleanup_worker()
        self.accept()


