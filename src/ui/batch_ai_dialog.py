from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt  # type: ignore[import]
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QMessageBox  # type: ignore[import]

from ..services.ai_analysis_service import AIAnalysisService, AnalysisContext, AIConfig


class _BatchWorker(QObject):
    progress = pyqtSignal(int, str)            # 0~100, message
    item_progress = pyqtSignal(int, int)      # current_index+1, total
    item_done = pyqtSignal(str, dict)         # path, data
    item_failed = pyqtSignal(str, str)        # path, error
    finished = pyqtSignal()

    def __init__(self, files: List[str], build_cfg: Callable[[], AIConfig], build_ctx: Callable[[], AnalysisContext], skip_if_cached: bool, delay_ms: int = 0, workers: int = 1, retry_count: int = 0, retry_delay_ms: int = 0):
        super().__init__()
        self._files = files
        self._build_cfg = build_cfg
        self._build_ctx = build_ctx
        self._skip_cached = bool(skip_if_cached)
        self._pause = False
        self._cancel = False
        self._service = AIAnalysisService()
        try:
            self._delay_ms = int(max(0, delay_ms))
        except Exception:
            self._delay_ms = 0
        try:
            self._workers = max(1, int(workers))
        except Exception:
            self._workers = 1
        try:
            self._retry_count = max(0, int(retry_count))
        except Exception:
            self._retry_count = 0
        try:
            self._retry_delay_ms = max(0, int(retry_delay_ms))
        except Exception:
            self._retry_delay_ms = 0

    def pause(self):
        self._pause = True

    def resume(self):
        self._pause = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            cfg = self._build_cfg()
            ctx = self._build_ctx()
            total = len(self._files)
            if total <= 0:
                self.finished.emit()
                return
            # 병렬 실행
            try:
                import concurrent.futures as _fut
            except Exception:
                _fut = None  # type: ignore
            done_cnt = 0
            if _fut is None or self._workers <= 1:
                # 순차 폴백
                self._service.apply_config(cfg)
                for idx, path in enumerate(self._files):
                    if self._cancel:
                        break
                    self.item_progress.emit(idx + 1, total)
                    while self._pause and not self._cancel:
                        QThread.msleep(50)
                    if not path or not os.path.isfile(path):
                        self.item_failed.emit(path, "파일 없음")
                        continue
                    # 재시도 루프
                    attempts = 0
                    while True:
                        try:
                            data = self._service.analyze(path, context=ctx, progress_cb=None, is_cancelled=lambda: self._cancel)
                            self.item_done.emit(path, data or {})
                            break
                        except Exception as e:
                            attempts += 1
                            if attempts > int(self._retry_count) or self._cancel:
                                self.item_failed.emit(path, str(e))
                                break
                            if int(self._retry_delay_ms) > 0:
                                QThread.msleep(int(self._retry_delay_ms))
                    done_cnt += 1
                    self.progress.emit(int(done_cnt * 100 / max(1, total)), f"{done_cnt}/{total} 완료")
                    if int(self._delay_ms) > 0 and done_cnt < total and not self._cancel:
                        QThread.msleep(int(self._delay_ms))
            else:
                # 스레드 풀
                def _task(p: str) -> tuple[str, Dict[str, Any] | None, str | None]:
                    try:
                        svc = AIAnalysisService()
                        svc.apply_config(cfg)
                        if not p or not os.path.isfile(p):
                            return p, None, "파일 없음"
                        attempts = 0
                        while True:
                            try:
                                data = svc.analyze(p, context=ctx, progress_cb=None, is_cancelled=lambda: self._cancel)
                                return p, (data or {}), None
                            except Exception as e:
                                attempts += 1
                                if attempts > int(self._retry_count):
                                    return p, None, str(e)
                                if int(self._retry_delay_ms) > 0:
                                    QThread.msleep(int(self._retry_delay_ms))
                    except Exception as e:
                        return p, None, str(e)
                # 제출
                with _fut.ThreadPoolExecutor(max_workers=self._workers) as ex:
                    futures = []
                    for i, path in enumerate(self._files):
                        if self._cancel:
                            break
                        self.item_progress.emit(i + 1, total)
                        while self._pause and not self._cancel:
                            QThread.msleep(50)
                        futures.append(ex.submit(_task, path))
                        if int(self._delay_ms) > 0 and (i + 1) < total and not self._cancel:
                            QThread.msleep(int(self._delay_ms))
                    for fut in _fut.as_completed(futures):
                        if self._cancel:
                            break
                        p, data, err = fut.result()
                        if err is None and isinstance(data, dict):
                            self.item_done.emit(p, data)
                        else:
                            self.item_failed.emit(p, err or "실패")
                        done_cnt += 1
                        self.progress.emit(int(done_cnt * 100 / max(1, total)), f"{done_cnt}/{total} 완료")
        finally:
            self.finished.emit()


class BatchAIDialog(QDialog):
    def __init__(self, viewer):
        super().__init__(viewer)
        self.setWindowTitle("배치 AI 분석")
        self._viewer = viewer
        self._thread: Optional[QThread] = None
        self._worker: Optional[_BatchWorker] = None
        self._failed: List[str] = []
        self._results: Dict[str, dict] = {}

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(6)
        except Exception:
            pass

        self.lbl = QLabel("대상 파일: 0")
        root.addWidget(self.lbl)
        self.bar = QProgressBar(self)
        self.bar.setRange(0, 100)
        root.addWidget(self.bar)
        self.cur = QLabel("준비 중…", self)
        try:
            self.cur.setStyleSheet("color: #BEBEBE;")
        except Exception:
            pass
        root.addWidget(self.cur)

        row = QHBoxLayout()
        self.start_btn = QPushButton("시작")
        self.pause_btn = QPushButton("일시정지")
        self.resume_btn = QPushButton("재개")
        self.retry_btn = QPushButton("실패 재시도")
        self.stop_btn = QPushButton("중지")
        self.close_btn = QPushButton("닫기")
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.retry_btn.setEnabled(False)
        row.addWidget(self.start_btn)
        row.addWidget(self.pause_btn)
        row.addWidget(self.resume_btn)
        row.addWidget(self.retry_btn)
        row.addStretch(1)
        row.addWidget(self.stop_btn)
        row.addWidget(self.close_btn)
        root.addLayout(row)

        self.start_btn.clicked.connect(self._on_start)
        self.pause_btn.clicked.connect(self._on_pause)
        self.resume_btn.clicked.connect(self._on_resume)
        self.retry_btn.clicked.connect(self._on_retry)
        self.stop_btn.clicked.connect(self._on_stop)
        self.close_btn.clicked.connect(self._on_close)
        # 단축키: 일시정지/재개/중지
        try:
            from PyQt6.QtGui import QShortcut, QKeySequence  # type: ignore[import]
            sc_p = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
            sc_p.activated.connect(self._on_pause)
            sc_r = QShortcut(QKeySequence("Ctrl+Shift+R"), self)
            sc_r.activated.connect(self._on_resume)
            sc_x = QShortcut(QKeySequence("Ctrl+Shift+X"), self)
            sc_x.activated.connect(self._on_stop)
        except Exception:
            pass

        # 초기 파일 리스트
        files = getattr(viewer, "image_files_in_dir", []) or []
        self._all_files = [p for p in files if p and os.path.isfile(p)]
        self.lbl.setText(f"대상 파일: {len(self._all_files)}")

    def _on_start(self):
        if self._thread is not None:
            return
        if not self._all_files:
            QMessageBox.information(self, "배치 분석", "대상 파일이 없습니다.")
            return
        self._failed.clear()
        self._results.clear()
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.retry_btn.setEnabled(False)
        self._thread = QThread()
        skip_if_cached = bool(getattr(self._viewer, "_ai_skip_if_cached", False))
        try:
            delay_ms = int(getattr(self._viewer, "_ai_batch_delay_ms", 0))
        except Exception:
            delay_ms = 0
        try:
            workers = int(getattr(self._viewer, "_ai_batch_workers", 4))
        except Exception:
            workers = 4
        try:
            rcount = int(getattr(self._viewer, "_ai_batch_retry_count", 0))
        except Exception:
            rcount = 0
        try:
            rdelay = int(getattr(self._viewer, "_ai_batch_retry_delay_ms", 0))
        except Exception:
            rdelay = 0
        self._worker = _BatchWorker(self._all_files, self._build_cfg_from_viewer, self._build_ctx_from_viewer, skip_if_cached, delay_ms=delay_ms, workers=workers, retry_count=rcount, retry_delay_ms=rdelay)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.item_progress.connect(self._on_item_progress)
        self._worker.item_done.connect(self._on_item_done)
        self._worker.item_failed.connect(self._on_item_failed)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _on_pause(self):
        try:
            if self._worker:
                self._worker.pause()
                self.pause_btn.setEnabled(False)
                self.resume_btn.setEnabled(True)
        except Exception:
            pass

    def _on_resume(self):
        try:
            if self._worker:
                self._worker.resume()
                self.resume_btn.setEnabled(False)
                self.pause_btn.setEnabled(True)
        except Exception:
            pass

    def _on_stop(self):
        try:
            if self._worker:
                self._worker.cancel()
        except Exception:
            pass

    def _on_close(self):
        self._on_stop()
        try:
            if self._thread:
                self._thread.quit()
                self._thread.wait(3000)
        except Exception:
            pass
        self.accept()

    def _on_progress(self, p: int, msg: str):
        try:
            self.bar.setValue(max(0, min(100, int(p))))
        except Exception:
            pass
        if msg:
            try:
                self.cur.setText(str(msg))
            except Exception:
                pass

    def _on_item_progress(self, cur: int, total: int):
        self.lbl.setText(f"대상 파일: {total} — 진행 {cur}/{total}")

    def _on_item_done(self, path: str, data: dict):
        self._results[path] = data or {}
        try:
            name = os.path.basename(path)
            self.cur.setText(f"완료: {name}")
        except Exception:
            pass

    def _on_item_failed(self, path: str, err: str):
        self._failed.append(path)
        try:
            name = os.path.basename(path) if path else "(unknown)"
            self.cur.setText(f"실패: {name}")
        except Exception:
            pass

    def _on_finished(self):
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        if self._failed:
            self.retry_btn.setEnabled(True)
            try:
                self.cur.setText(f"실패 {len(self._failed)}건 — 재시도 가능")
            except Exception:
                pass
        else:
            try:
                self.cur.setText("모든 작업이 완료되었습니다.")
            except Exception:
                pass
        try:
            if self._thread:
                self._thread.quit()
                self._thread.wait(2000)
        except Exception:
            pass
        self._thread = None
        self._worker = None

    def _on_retry(self):
        if not self._failed:
            return
        self._all_files = list(self._failed)
        self._failed = []
        self._on_start()

    def _build_ctx_from_viewer(self) -> AnalysisContext:
        v = self._viewer
        try:
            lang = str(getattr(v, "_ai_language", "ko") or "ko")
        except Exception:
            lang = "ko"
        try:
            tone = str(getattr(v, "_ai_tone", "중립") or "중립")
        except Exception:
            tone = "중립"
        try:
            purpose = str(getattr(v, "_ai_purpose", "archive") or "archive")
        except Exception:
            purpose = "archive"
        try:
            sc = int(getattr(v, "_ai_short_words", 16))
        except Exception:
            sc = 16
        try:
            lc = int(getattr(v, "_ai_long_chars", 120))
        except Exception:
            lc = 120
        return AnalysisContext(purpose=purpose, tone=tone, language=lang, long_caption_chars=lc, short_caption_words=sc)

    def _build_cfg_from_viewer(self) -> AIConfig:
        v = self._viewer
        cfg = AIConfig()
        try:
            cfg.api_key = str(getattr(v, "_ai_openai_api_key", "") or "")
        except Exception:
            cfg.api_key = ""
        cfg.provider = "openai"
        try:
            cfg.fast_mode = bool(getattr(v, "_ai_fast_mode", False))
        except Exception:
            cfg.fast_mode = False
        try:
            cfg.exif_level = str(getattr(v, "_ai_exif_level", "full"))
        except Exception:
            cfg.exif_level = "full"
        try:
            cfg.retry_count = int(getattr(v, "_ai_retry_count", 2))
        except Exception:
            cfg.retry_count = 2
        try:
            cfg.retry_delay_s = float(int(getattr(v, "_ai_retry_delay_ms", 800)) / 1000.0)
        except Exception:
            cfg.retry_delay_s = 0.8
        try:
            cfg.cache_enable = True
            cfg.cache_ttl_s = int(getattr(v, "_ai_cache_ttl_s", 0)) if hasattr(v, "_ai_cache_ttl_s") else 0
        except Exception:
            pass
        return cfg


