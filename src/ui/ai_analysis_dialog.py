from __future__ import annotations

import json
import os
from typing import Any, Dict

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QPlainTextEdit, QWidget, QTabWidget, QMessageBox, QFileDialog
)  # type: ignore[import]
from PyQt6.QtCore import Qt  # type: ignore[import]

from ..services.ai_analysis_service import AIAnalysisService, AnalysisContext
from ..utils.logging_setup import get_logger

_log = get_logger("ui.AIAnalysisDialog")


class AIAnalysisDialog(QDialog):
    def __init__(self, parent=None, image_path: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("AI 분석")
        self._image_path = image_path or ""
        self._service = AIAnalysisService()
        self._data: Dict[str, Any] = {}

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

        # Tabs: Summary(JSON) and Captions
        self.tabs = QTabWidget(self)
        root.addWidget(self.tabs, 1)

        # JSON view
        self.json_edit = QPlainTextEdit(self)
        try:
            self.json_edit.setReadOnly(True)
        except Exception:
            pass
        self.tabs.addTab(self.json_edit, "JSON")

        # Captions view
        self.captions_view = QTextEdit(self)
        try:
            self.captions_view.setReadOnly(True)
        except Exception:
            pass
        self.tabs.addTab(self.captions_view, "요약")

        # Buttons
        btn_row = QHBoxLayout()
        self.analyze_btn = QPushButton("분석 실행")
        self.analyze_btn.clicked.connect(self._on_analyze)
        btn_row.addWidget(self.analyze_btn)

        copy_btn = QPushButton("JSON 복사")
        copy_btn.clicked.connect(self._copy_json)
        btn_row.addWidget(copy_btn)

        save_btn = QPushButton("JSON 저장")
        save_btn.clicked.connect(self._save_json)
        btn_row.addWidget(save_btn)

        btn_row.addStretch(1)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        if self._image_path:
            # 자동 1회 분석 실행 (UX 단순화)
            try:
                self._on_analyze()
            except Exception:
                pass

    def _on_analyze(self):
        if not self._image_path or not os.path.exists(self._image_path):
            QMessageBox.warning(self, "AI 분석", "유효한 파일이 없습니다.")
            return
        try:
            ctx = AnalysisContext()
            data = self._service.analyze(self._image_path, context=ctx)
            self._data = data
            self._render(data)
        except Exception as e:
            try:
                _log.error("analyze_fail | err=%s", str(e))
            except Exception:
                pass
            QMessageBox.warning(self, "AI 분석", f"분석 실패: {e}")

    def _render(self, data: Dict[str, Any]):
        try:
            self.json_edit.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception:
            self.json_edit.setPlainText("{}")
        # Captions summary
        sc = str(data.get("short_caption") or "").strip()
        lc = str(data.get("long_caption") or "").strip()
        tags = data.get("tags") or []
        subj = data.get("subjects") or []
        lines = []
        if sc:
            lines.append(f"short: {sc}")
        if lc:
            lines.append("")
            lines.append(lc)
        if tags:
            lines.append("")
            lines.append("tags: " + ", ".join([str(t) for t in tags]))
        if subj:
            lines.append("subjects: " + ", ".join([str(s) for s in subj]))
        self.captions_view.setPlainText("\n".join(lines))

    def _copy_json(self):
        try:
            from PyQt6.QtWidgets import QApplication  # type: ignore
            cb = QApplication.clipboard()
            cb.setText(self.json_edit.toPlainText())
            QMessageBox.information(self, "AI 분석", "JSON을 클립보드에 복사했습니다.")
        except Exception:
            pass

    def _save_json(self):
        try:
            text = self.json_edit.toPlainText()
            data = json.loads(text) if text.strip() else (self._data or {})
        except Exception:
            QMessageBox.warning(self, "AI 분석", "JSON 형식이 올바르지 않습니다.")
            return
        if not self._validate_schema(data):
            QMessageBox.warning(self, "AI 분석", "스키마가 불완전합니다. 저장을 계속합니다.")
        path, _ = QFileDialog.getSaveFileName(self, "JSON 저장", os.path.splitext(self._image_path or "result")[0] + "_analysis.json", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "AI 분석", "JSON을 저장했습니다.")
        except Exception as e:
            QMessageBox.warning(self, "AI 분석", f"저장 실패: {e}")

    def _validate_schema(self, data: Dict[str, Any]) -> bool:
        try:
            ok = True
            ok = ok and isinstance(data.get("short_caption", ""), str)
            ok = ok and isinstance(data.get("long_caption", ""), str)
            ok = ok and isinstance(data.get("tags", []), list)
            ok = ok and isinstance(data.get("subjects", []), list)
            cam = data.get("camera_settings", {})
            ok = ok and isinstance(cam, dict)
            gps = data.get("gps", {})
            ok = ok and isinstance(gps, dict)
            safety = data.get("safety", {"nsfw": False, "sensitive": []})
            ok = ok and isinstance(safety, dict)
            ok = ok and isinstance(data.get("confidence", 0.0), (int, float))
            ok = ok and isinstance(data.get("notes", ""), str)
            return bool(ok)
        except Exception:
            return False


