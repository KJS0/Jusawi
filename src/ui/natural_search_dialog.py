from __future__ import annotations

import os
from typing import List, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QWidget
)  # type: ignore[import]
from PyQt6.QtCore import Qt, QSize  # type: ignore[import]
from PyQt6.QtGui import QIcon, QPixmap, QPainter  # type: ignore[import]

from ..services.embeddings_service import EmbeddingsService
from ..services.verifier_service import VerifierService


class NaturalSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("자연어 검색")
        self._svc = EmbeddingsService()
        self._verifier = VerifierService()
        self._offline = None  # 제거 예정(온라인 GPT만 사용)
        self._viewer = parent

        # ----- UI 구성 -----
        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(6)
        except Exception:
            pass

        row = QHBoxLayout()
        row.addWidget(QLabel("질의:"))
        self.query_edit = QLineEdit(self)
        row.addWidget(self.query_edit, 1)
        self.btn_search = QPushButton("검색")
        self.btn_search.clicked.connect(self._on_search)
        row.addWidget(self.btn_search)
        # 인덱스 업데이트/베스트 열기 제거 (자동 업데이트/더블클릭 사용)
        root.addLayout(row)

        # 추천 질의 버튼들(초보자용)
        suggest = QHBoxLayout()
        for caption in ["노을", "해변", "인물", "야경", "숲길", "도심", "반려동물"]:
            btn = QPushButton(caption)
            btn.setFlat(True)
            btn.clicked.connect(lambda _, t=caption: self._on_suggest_click(t))
            suggest.addWidget(btn)
        suggest.addStretch(1)
        root.addLayout(suggest)

        # 상태 라벨 제거

        # 썸네일 그리드(윈도우 탐색기 스타일)
        self.grid = QListWidget(self)
        try:
            self.grid.setViewMode(self.grid.ViewMode.IconMode)
            self.grid.setResizeMode(self.grid.ResizeMode.Adjust)
            self.grid.setMovement(self.grid.Movement.Static)
            self.grid.setSpacing(8)
            self.grid.setIconSize(QSize(128, 128))
            self.grid.setUniformItemSizes(True)
            self.grid.setWordWrap(True)
            self.grid.itemDoubleClicked.connect(lambda _: self._on_open_selected())
            self.grid.itemSelectionChanged.connect(self._on_list_selection_changed)
            # 단일 클릭 시에도 미리보기 즉시 갱신
            try:
                self.grid.itemClicked.connect(self._on_item_clicked)
                self.grid.currentItemChanged.connect(lambda cur, prev: self._on_item_clicked(cur))
            except Exception:
                pass
        except Exception:
            pass

        main_row = QHBoxLayout()
        main_row.addWidget(self.grid, 1)

        preview = QVBoxLayout()
        self.preview_label = QLabel("미리보기", self)
        try:
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        except Exception:
            pass
        self.preview_pix = QLabel(self)
        try:
            self.preview_pix.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_pix.setMinimumSize(200, 200)
        except Exception:
            pass
        self.preview_path = QLabel("", self)
        try:
            self.preview_path.setWordWrap(True)
        except Exception:
            pass
        preview.addWidget(self.preview_label)
        preview.addWidget(self.preview_pix, 1)
        preview.addWidget(self.preview_path)
        holder = QWidget(self)
        holder.setLayout(preview)
        holder.setMinimumWidth(240)
        main_row.addWidget(holder)
        root.addLayout(main_row, 1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_close = QPushButton("닫기")
        self.btn_close.clicked.connect(self.accept)
        btns.addWidget(self.btn_close)
        root.addLayout(btns)

        # 오프라인 예열 제거

    def _ensure_offline(self):
        return None

    def _on_search(self):
        q = self.query_edit.text().strip()
        if not q:
            QMessageBox.information(self, "자연어 검색", "질의를 입력하세요.")
            return
        try:
            # 항상 현재 폴더 기준으로 인덱싱(업서트) 시도 후 검색
            files = getattr(self._viewer, "image_files_in_dir", []) or []
            if not files:
                QMessageBox.information(self, "자연어 검색", "현재 폴더에 인덱싱할 이미지가 없습니다.")
                return
            files_set = set(files)
            # 간단 대기 커서 처리
            try:
                from PyQt6.QtWidgets import QApplication  # type: ignore[import]
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            except Exception:
                QApplication = None  # type: ignore
            try:
                self._svc.index_paths(list(files))  # 변경/미인덱스 항목만 업서트됨
            finally:
                try:
                    if 'QApplication' in locals() and QApplication:
                        QApplication.restoreOverrideCursor()
                except Exception:
                    pass
            topk = 100
            # 온라인 임베딩(GPT) 검색
            # 충분한 후보를 먼저 받고, 현재 폴더 파일만 필터링
            raw = self._svc.query(q, top_k=topk * 5)
            results = [(p, s) for (p, s) in raw if p in files_set][:topk]
            # 임베딩 상위 결과를 GPT 비전으로 재검증(필터+재정렬) - 병렬 처리
            verified = []
            try:
                import concurrent.futures
            except Exception:
                concurrent = None  # type: ignore
            # 상위 후보 N만 검증(환경변수로 조정)
            try:
                import os as _os
                max_verify = int(_os.getenv("AI_VERIFY_TOP", "24") or 24)
            except Exception:
                max_verify = 24
            to_check = results[: max(1, int(max_verify))]
            # 동시성 제한(기본 4)
            try:
                import os as _os2
                workers = int(_os2.getenv("AI_VERIFY_CONCURRENCY", "8") or 8)
                workers = max(1, min(8, workers))
            except Exception:
                workers = 4

            def _task(item):
                p, sim = item
                try:
                    vr = self._verifier.verify(p, q)
                    match = bool(vr.get("match", False))
                    conf = float(vr.get("confidence", 0.0))
                    if match and conf >= 0.6:
                        score = conf * 0.9 + float(sim) * 0.1
                        return (p, score)
                except Exception:
                    return None
                return None

            if 'concurrent' in locals() and concurrent:
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                        for res in ex.map(_task, to_check):
                            if res:
                                verified.append(res)
                except Exception:
                    # 실패 시 순차 폴백
                    for it in to_check:
                        r = _task(it)
                        if r:
                            verified.append(r)
            else:
                for it in to_check:
                    r = _task(it)
                    if r:
                        verified.append(r)
            verified.sort(key=lambda x: x[1], reverse=True)
            self._fill_results(verified or results)
        except Exception as e:
            QMessageBox.warning(self, "자연어 검색", f"검색 실패: {e}")

    # ----- 비동기 예열 -----
    # 오프라인 예열/스레드 로직 제거 (온라인 전용)

    def _fill_results(self, items: List[Tuple[str, float]]):
        try:
            self.grid.clear()
        except Exception:
            pass
        for path, score in items:
            base = os.path.basename(path)
            item = QListWidgetItem(base)
            # 썸네일 아이콘
            try:
                thumb = self._make_thumb_icon(path, QSize(160, 90))
                if thumb is not None:
                    item.setIcon(thumb)
            except Exception:
                pass
            try:
                item.setData(Qt.ItemDataRole.UserRole, path)
            except Exception:
                pass
            self.grid.addItem(item)
        # 첫 항목 선택 및 미리보기 갱신
        try:
            if self.grid.count() > 0:
                self.grid.setCurrentRow(0)
                self._update_preview_from_index(0)
        except Exception:
            pass

    def _on_open_selected(self):
        row = self.grid.currentRow()
        if row < 0:
            return
        it = self.grid.item(row)
        path = it.data(Qt.ItemDataRole.UserRole) if it else ""
        try:
            if getattr(self._viewer, "load_image", None):
                self._viewer.load_image(path)
                self.accept()
        except Exception:
            pass

    def _on_suggest_click(self, text: str):
        try:
            self.query_edit.setText(text)
            self._on_search()
        except Exception:
            pass

    def _update_preview_from_index(self, r: int):
        try:
            if r < 0 or r >= self.grid.count():
                return
            it = self.grid.item(r)
            path = it.data(Qt.ItemDataRole.UserRole) if it else ""
            self.preview_label.setText(os.path.basename(path))
            self.preview_path.setText(path)
            pm = self._make_thumb_pixmap(path, QSize(264, 148))  # 16:9 미리보기
            if pm is not None and not pm.isNull():
                self.preview_pix.setPixmap(pm)
            else:
                self.preview_pix.clear()
        except Exception:
            pass

    def _on_list_selection_changed(self):
        try:
            row = self.grid.currentRow()
            self._update_preview_from_index(row)
        except Exception:
            pass

    def _on_item_clicked(self, item):
        try:
            if not item:
                return
            row = self.grid.row(item)
            self._update_preview_from_index(int(row))
        except Exception:
            pass

    def _make_thumb_pixmap(self, path: str, size: QSize) -> QPixmap | None:
        try:
            src = QPixmap(path)
            if src.isNull():
                return None
            canvas = QPixmap(size)
            canvas.fill(Qt.GlobalColor.black)
            scaled = src.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            x = int((size.width() - scaled.width()) / 2)
            y = int((size.height() - scaled.height()) / 2)
            p = QPainter(canvas)
            try:
                p.drawPixmap(x, y, scaled)
            finally:
                p.end()
            return canvas
        except Exception:
            return None

    def _make_thumb_icon(self, path: str, size: QSize) -> QIcon | None:
        pm = self._make_thumb_pixmap(path, size)
        return QIcon(pm) if pm is not None else None


