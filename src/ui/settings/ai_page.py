from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QComboBox, QSpinBox, QFormLayout,
)

from .base import SettingsPage


class AISettingsPage(SettingsPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        try:
            # 일반 탭 수준으로 여백/간격 표준화
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(8)
        except Exception:
            pass

        # 헤더 라벨을 제거해 상단 여백 낭비를 줄임

        self.chk_ai_auto = QCheckBox("AI 분석 자동 실행(열기)", self)
        self.chk_ai_auto_drop = QCheckBox("AI 분석 자동 실행(드롭)", self)
        self.chk_ai_auto_nav = QCheckBox("AI 분석 자동 실행(이전/다음 이동)", self)
        self.chk_ai_skip_cached = QCheckBox("이미 분석된 사진은 건너뛰기", self)
        self.spin_ai_delay = QSpinBox(self); self.spin_ai_delay.setRange(0, 60000); self.spin_ai_delay.setSuffix(" ms")
        form_auto = QFormLayout()
        form_auto.addRow("자동 실행(열기)", self.chk_ai_auto)
        form_auto.addRow("자동 실행(드롭)", self.chk_ai_auto_drop)
        form_auto.addRow("자동 실행(이동)", self.chk_ai_auto_nav)
        form_auto.addRow("캐시 시 건너뛰기", self.chk_ai_skip_cached)
        form_auto.addRow("지연 시간", self.spin_ai_delay)
        try:
            form_auto.setContentsMargins(0, 0, 0, 0)
            form_auto.setSpacing(4)
            try:
                form_auto.setHorizontalSpacing(8)
                form_auto.setVerticalSpacing(4)
            except Exception:
                pass
            form_auto.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            form_auto.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            try:
                from PyQt6.QtWidgets import QLayout  # type: ignore[import]
                form_auto.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
            except Exception:
                pass
        except Exception:
            pass
        # 자동 실행 섹션을 그룹화해 과도한 세로 공간 사용을 방지
        try:
            from PyQt6.QtWidgets import QGroupBox  # type: ignore[import]
            gb_auto = QGroupBox(self)
            gb_auto.setTitle("")
            lay = QVBoxLayout(gb_auto)
            try:
                lay.setContentsMargins(0, 0, 0, 0)
                lay.setSpacing(4)
            except Exception:
                pass
            lay.addLayout(form_auto)
            root.addWidget(gb_auto)
        except Exception:
            root.addLayout(form_auto)

        # 두 번째 헤더도 제거해 섹션 간격을 축소

        from PyQt6.QtWidgets import QLineEdit as _QLineEditAI  # type: ignore[import]
        self.combo_ai_language = QComboBox(self)
        self.combo_ai_language.addItems(["한국어", "영어"])
        self.combo_ai_tone = QComboBox(self)
        self.combo_ai_tone.addItems(["중립", "친근한", "공식적인"])  # tone
        self.combo_ai_purpose = QComboBox(self)
        self.combo_ai_purpose.addItems(["기록용", "SNS용", "블로그용"])  # archive|sns|blog
        self.spin_ai_short_words = QSpinBox(self); self.spin_ai_short_words.setRange(4, 32); self.spin_ai_short_words.setSuffix(" 단어")
        self.spin_ai_long_chars = QSpinBox(self); self.spin_ai_long_chars.setRange(40, 400); self.spin_ai_long_chars.setSuffix(" 자")
        self.chk_ai_fast_mode = QCheckBox("빠른 모드(Fast)", self)
        self.combo_ai_exif_level = QComboBox(self)
        self.combo_ai_exif_level.addItems(["상세", "요약", "사용 안 함"])  # full|summary|none
        self.spin_ai_retry_count = QSpinBox(self); self.spin_ai_retry_count.setRange(0, 5); self.spin_ai_retry_count.setSuffix(" 회")
        try:
            self.spin_ai_retry_count.setToolTip("0으로 두면 재시도하지 않습니다. 1 권장")
        except Exception:
            pass
        self.spin_ai_retry_delay = QSpinBox(self); self.spin_ai_retry_delay.setRange(0, 5000); self.spin_ai_retry_delay.setSuffix(" ms")
        self.ed_ai_api_key = _QLineEditAI(self)
        try:
            from PyQt6.QtWidgets import QLineEdit as _QLE  # type: ignore[import]
            self.ed_ai_api_key.setEchoMode(_QLE.EchoMode.Normal)
        except Exception:
            pass
        form_ai = QFormLayout()
        form_ai.addRow("출력 언어", self.combo_ai_language)
        form_ai.addRow("톤/스타일", self.combo_ai_tone)
        form_ai.addRow("목적", self.combo_ai_purpose)
        form_ai.addRow("짧은 캡션 단어 수", self.spin_ai_short_words)
        form_ai.addRow("긴 캡션 글자 수", self.spin_ai_long_chars)
        form_ai.addRow("빠른 모드", self.chk_ai_fast_mode)
        form_ai.addRow("EXIF 활용", self.combo_ai_exif_level)
        form_ai.addRow("재시도 횟수", self.spin_ai_retry_count)
        form_ai.addRow("재시도 지연", self.spin_ai_retry_delay)
        form_ai.addRow("GPT API 키", self.ed_ai_api_key)
        try:
            form_ai.setContentsMargins(0, 0, 0, 0)
            form_ai.setSpacing(4)
            try:
                form_ai.setHorizontalSpacing(8)
                form_ai.setVerticalSpacing(4)
            except Exception:
                pass
            form_ai.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            form_ai.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            try:
                from PyQt6.QtWidgets import QLayout  # type: ignore[import]
                form_ai.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
            except Exception:
                pass
        except Exception:
            pass
        try:
            from PyQt6.QtWidgets import QGroupBox  # type: ignore[import]
            gb_ai = QGroupBox(self)
            gb_ai.setTitle("")
            lay2 = QVBoxLayout(gb_ai)
            try:
                lay2.setContentsMargins(0, 0, 0, 0)
                lay2.setSpacing(4)
            except Exception:
                pass
            lay2.addLayout(form_ai)
            root.addWidget(gb_ai)
        except Exception:
            root.addLayout(form_ai)

        # 고급/배치/검색/프라이버시 설정 섹션
        try:
            from PyQt6.QtWidgets import QGroupBox, QDoubleSpinBox  # type: ignore[import]
            gb_adv = QGroupBox(self)
            gb_adv.setTitle("")
            form_adv = QFormLayout(gb_adv)
            try:
                form_adv.setContentsMargins(0, 0, 0, 0)
                form_adv.setSpacing(4)
                form_adv.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            except Exception:
                pass
            # 출력 정책: 신뢰도 임계/적용 정책
            self.spin_conf_thresh = QSpinBox(self); self.spin_conf_thresh.setRange(0, 100); self.spin_conf_thresh.setSuffix(" %")
            self.combo_apply_policy = QComboBox(self); self.combo_apply_policy.addItems(["자동 적용", "보류", "리뷰 큐"])
            form_adv.addRow("신뢰도 임계값", self.spin_conf_thresh)
            form_adv.addRow("임계 시 동작", self.combo_apply_policy)
            # 배치 성능
            self.spin_batch_workers = QSpinBox(self); self.spin_batch_workers.setRange(1, 32)
            self.spin_batch_delay = QSpinBox(self); self.spin_batch_delay.setRange(0, 5000); self.spin_batch_delay.setSuffix(" ms")
            self.spin_batch_retry = QSpinBox(self); self.spin_batch_retry.setRange(0, 5); self.spin_batch_retry.setSuffix(" 회")
            self.spin_batch_retry_delay = QSpinBox(self); self.spin_batch_retry_delay.setRange(0, 5000); self.spin_batch_retry_delay.setSuffix(" ms")
            form_adv.addRow("배치 동시 작업 수", self.spin_batch_workers)
            form_adv.addRow("배치 호출 간 지연", self.spin_batch_delay)
            form_adv.addRow("배치 최대 재시도", self.spin_batch_retry)
            form_adv.addRow("배치 재시도 지연", self.spin_batch_retry_delay)
            # 검색/유사도 기본값
            self.combo_verify_mode_default = QComboBox(self); self.combo_verify_mode_default.addItems(["엄격", "보통", "느슨함"])  # strict/normal/loose
            self.spin_verify_topn_default = QSpinBox(self); self.spin_verify_topn_default.setRange(0, 500)
            self.spin_tag_weight = QSpinBox(self); self.spin_tag_weight.setRange(1, 5)
            self.spin_bg_index_max = QSpinBox(self); self.spin_bg_index_max.setRange(10, 100000)
            form_adv.addRow("검색 재검증 모드(기본)", self.combo_verify_mode_default)
            form_adv.addRow("검색 상위 N(기본)", self.spin_verify_topn_default)
            form_adv.addRow("태그 가중치", self.spin_tag_weight)
            form_adv.addRow("폴더 진입 색인 최대", self.spin_bg_index_max)
            # 프라이버시/네트워크
            self.chk_privacy_hide_loc = QCheckBox("위치 숨김(주소/지도 차단)", self)
            self.chk_offline_mode = QCheckBox("오프라인 모드(외부 호출 차단)", self)
            self.spin_http_timeout = QSpinBox(self); self.spin_http_timeout.setRange(1, 600); self.spin_http_timeout.setSuffix(" s")
            form_adv.addRow("프라이버시", self.chk_privacy_hide_loc)
            form_adv.addRow("오프라인 모드", self.chk_offline_mode)
            form_adv.addRow("HTTP 타임아웃", self.spin_http_timeout)
            root.addLayout(form_adv)
        except Exception:
            pass

    def load_from_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            self.chk_ai_auto.setChecked(bool(getattr(viewer, "_auto_ai_on_open", False)))
        except Exception:
            self.chk_ai_auto.setChecked(False)
        try:
            self.chk_ai_auto_drop.setChecked(bool(getattr(viewer, "_auto_ai_on_drop", False)))
        except Exception:
            self.chk_ai_auto_drop.setChecked(False)
        try:
            self.chk_ai_auto_nav.setChecked(bool(getattr(viewer, "_auto_ai_on_nav", False)))
        except Exception:
            self.chk_ai_auto_nav.setChecked(False)
        try:
            self.chk_ai_skip_cached.setChecked(bool(getattr(viewer, "_ai_skip_if_cached", False)))
        except Exception:
            self.chk_ai_skip_cached.setChecked(False)
        try:
            self.spin_ai_delay.setValue(int(getattr(viewer, "_auto_ai_delay_ms", 0)))
        except Exception:
            self.spin_ai_delay.setValue(0)
        # 기본값 그룹
        try:
            lang = str(getattr(viewer, "_ai_language", "ko"))
            self.combo_ai_language.setCurrentIndex(0 if lang.startswith("ko") else 1)
        except Exception:
            self.combo_ai_language.setCurrentIndex(0)
        try:
            tone = str(getattr(viewer, "_ai_tone", "중립"))
            idx = {"중립":0, "친근한":1, "공식적인":2}.get(tone, 0)
            self.combo_ai_tone.setCurrentIndex(idx)
        except Exception:
            self.combo_ai_tone.setCurrentIndex(0)
        try:
            pur = str(getattr(viewer, "_ai_purpose", "archive"))
            idx = {"archive":0, "sns":1, "blog":2}.get(pur, 0)
            self.combo_ai_purpose.setCurrentIndex(idx)
        except Exception:
            self.combo_ai_purpose.setCurrentIndex(0)
        try:
            self.spin_ai_short_words.setValue(int(getattr(viewer, "_ai_short_words", 16)))
        except Exception:
            self.spin_ai_short_words.setValue(16)
        try:
            self.spin_ai_long_chars.setValue(int(getattr(viewer, "_ai_long_chars", 120)))
        except Exception:
            self.spin_ai_long_chars.setValue(120)
        try:
            self.chk_ai_fast_mode.setChecked(bool(getattr(viewer, "_ai_fast_mode", False)))
        except Exception:
            self.chk_ai_fast_mode.setChecked(False)
        try:
            exif = str(getattr(viewer, "_ai_exif_level", "full"))
            self.combo_ai_exif_level.setCurrentIndex({"full":0, "summary":1, "none":2}.get(exif, 0))
        except Exception:
            self.combo_ai_exif_level.setCurrentIndex(0)
        try:
            self.spin_ai_retry_count.setValue(int(getattr(viewer, "_ai_retry_count", 2)))
        except Exception:
            self.spin_ai_retry_count.setValue(2)
        try:
            self.spin_ai_retry_delay.setValue(int(getattr(viewer, "_ai_retry_delay_ms", 800)))
        except Exception:
            self.spin_ai_retry_delay.setValue(800)
        try:
            self.ed_ai_api_key.setText(str(getattr(viewer, "_ai_openai_api_key", "") or ""))
        except Exception:
            self.ed_ai_api_key.setText("")
        # 확장 로드
        try:
            self.spin_conf_thresh.setValue(int(getattr(viewer, "_ai_conf_threshold_pct", 80)))
        except Exception:
            self.spin_conf_thresh.setValue(80)
        try:
            pol = str(getattr(viewer, "_ai_apply_policy", "보류"))
            self.combo_apply_policy.setCurrentIndex({"자동 적용":0, "보류":1, "리뷰 큐":2}.get(pol, 1))
        except Exception:
            self.combo_apply_policy.setCurrentIndex(1)
        try:
            self.spin_batch_workers.setValue(int(getattr(viewer, "_ai_batch_workers", 4)))
        except Exception:
            self.spin_batch_workers.setValue(4)
        try:
            self.spin_batch_delay.setValue(int(getattr(viewer, "_ai_batch_delay_ms", 0)))
        except Exception:
            self.spin_batch_delay.setValue(0)
        try:
            self.spin_batch_retry.setValue(int(getattr(viewer, "_ai_batch_retry_count", 0)))
        except Exception:
            self.spin_batch_retry.setValue(0)
        try:
            self.spin_batch_retry_delay.setValue(int(getattr(viewer, "_ai_batch_retry_delay_ms", 0)))
        except Exception:
            self.spin_batch_retry_delay.setValue(0)
        try:
            vm = str(getattr(viewer, "_search_verify_mode_default", "strict"))
            self.combo_verify_mode_default.setCurrentIndex({"strict":0, "normal":1, "loose":2}.get(vm, 0))
        except Exception:
            self.combo_verify_mode_default.setCurrentIndex(0)
        try:
            self.spin_verify_topn_default.setValue(int(getattr(viewer, "_search_verify_topn_default", 20)))
        except Exception:
            self.spin_verify_topn_default.setValue(20)
        try:
            self.spin_tag_weight.setValue(int(getattr(viewer, "_search_tag_weight", 2)))
        except Exception:
            self.spin_tag_weight.setValue(2)
        try:
            self.spin_bg_index_max.setValue(int(getattr(viewer, "_bg_index_max", 200)))
        except Exception:
            self.spin_bg_index_max.setValue(200)
        try:
            self.chk_privacy_hide_loc.setChecked(bool(getattr(viewer, "_privacy_hide_location", False)))
        except Exception:
            self.chk_privacy_hide_loc.setChecked(False)
        try:
            self.chk_offline_mode.setChecked(bool(getattr(viewer, "_offline_mode", False)))
        except Exception:
            self.chk_offline_mode.setChecked(False)
        try:
            self.spin_http_timeout.setValue(int(getattr(viewer, "_ai_http_timeout_s", 120)))
        except Exception:
            self.spin_http_timeout.setValue(120)

    def apply_to_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            viewer._auto_ai_on_open = bool(self.chk_ai_auto.isChecked())
        except Exception:
            pass
        try:
            viewer._auto_ai_on_drop = bool(self.chk_ai_auto_drop.isChecked())
        except Exception:
            pass
        try:
            viewer._auto_ai_on_nav = bool(self.chk_ai_auto_nav.isChecked())
        except Exception:
            pass
        try:
            viewer._ai_skip_if_cached = bool(self.chk_ai_skip_cached.isChecked())
        except Exception:
            pass
        try:
            viewer._auto_ai_delay_ms = int(self.spin_ai_delay.value())
        except Exception:
            pass
        try:
            viewer._ai_language = ("ko" if int(self.combo_ai_language.currentIndex()) == 0 else "en")
        except Exception:
            pass
        try:
            ti = int(self.combo_ai_tone.currentIndex())
            viewer._ai_tone = ("중립" if ti == 0 else ("친근한" if ti == 1 else "공식적인"))
        except Exception:
            pass
        try:
            pi = int(self.combo_ai_purpose.currentIndex())
            viewer._ai_purpose = ("archive" if pi == 0 else ("sns" if pi == 1 else "blog"))
        except Exception:
            pass
        try:
            viewer._ai_short_words = int(self.spin_ai_short_words.value())
        except Exception:
            pass
        try:
            viewer._ai_long_chars = int(self.spin_ai_long_chars.value())
        except Exception:
            pass
        try:
            viewer._ai_fast_mode = bool(self.chk_ai_fast_mode.isChecked())
        except Exception:
            pass
        try:
            ei = int(self.combo_ai_exif_level.currentIndex())
            viewer._ai_exif_level = ("full" if ei == 0 else ("summary" if ei == 1 else "none"))
        except Exception:
            pass
        try:
            viewer._ai_retry_count = int(self.spin_ai_retry_count.value())
        except Exception:
            pass
        try:
            viewer._ai_retry_delay_ms = int(self.spin_ai_retry_delay.value())
        except Exception:
            pass
        try:
            viewer._ai_openai_api_key = str(self.ed_ai_api_key.text()).strip()
        except Exception:
            pass
        # 확장 저장
        try:
            viewer._ai_conf_threshold_pct = int(self.spin_conf_thresh.value())
        except Exception:
            pass
        try:
            ap = int(self.combo_apply_policy.currentIndex())
            viewer._ai_apply_policy = ("자동 적용" if ap == 0 else ("보류" if ap == 1 else "리뷰 큐"))
        except Exception:
            pass
        try:
            viewer._ai_batch_workers = int(self.spin_batch_workers.value())
        except Exception:
            pass
        try:
            viewer._ai_batch_delay_ms = int(self.spin_batch_delay.value())
        except Exception:
            pass
        try:
            viewer._ai_batch_retry_count = int(self.spin_batch_retry.value())
        except Exception:
            pass
        try:
            viewer._ai_batch_retry_delay_ms = int(self.spin_batch_retry_delay.value())
        except Exception:
            pass
        try:
            vm = int(self.combo_verify_mode_default.currentIndex())
            viewer._search_verify_mode_default = ("strict" if vm == 0 else ("normal" if vm == 1 else "loose"))
        except Exception:
            pass
        try:
            viewer._search_verify_topn_default = int(self.spin_verify_topn_default.value())
        except Exception:
            pass
        try:
            viewer._search_tag_weight = int(self.spin_tag_weight.value())
        except Exception:
            pass
        try:
            viewer._bg_index_max = int(self.spin_bg_index_max.value())
        except Exception:
            pass
        try:
            viewer._privacy_hide_location = bool(self.chk_privacy_hide_loc.isChecked())
        except Exception:
            pass
        try:
            viewer._offline_mode = bool(self.chk_offline_mode.isChecked())
        except Exception:
            pass
        try:
            viewer._ai_http_timeout_s = int(self.spin_http_timeout.value())
        except Exception:
            pass

    def reset_to_defaults(self) -> None:
        try:
            self.chk_ai_auto.setChecked(False)
            self.chk_ai_auto_drop.setChecked(False)
            self.chk_ai_auto_nav.setChecked(False)
            self.chk_ai_skip_cached.setChecked(False)
            self.spin_ai_delay.setValue(0)
            self.combo_ai_language.setCurrentIndex(0)
            self.combo_ai_tone.setCurrentIndex(0)
            self.combo_ai_purpose.setCurrentIndex(0)
            self.spin_ai_short_words.setValue(16)
            self.spin_ai_long_chars.setValue(120)
            self.chk_ai_fast_mode.setChecked(False)
            self.combo_ai_exif_level.setCurrentIndex(0)
            self.spin_ai_retry_count.setValue(2)
            self.spin_ai_retry_delay.setValue(800)
            self.ed_ai_api_key.setText("")
        except Exception:
            pass
        try:
            self.spin_conf_thresh.setValue(80)
            self.combo_apply_policy.setCurrentIndex(1)
            self.spin_batch_workers.setValue(4)
            self.spin_batch_delay.setValue(0)
            self.spin_batch_retry.setValue(0)
            self.spin_batch_retry_delay.setValue(0)
            self.combo_verify_mode_default.setCurrentIndex(0)
            self.spin_verify_topn_default.setValue(20)
            self.spin_tag_weight.setValue(2)
            self.spin_bg_index_max.setValue(200)
            self.chk_privacy_hide_loc.setChecked(False)
            self.chk_offline_mode.setChecked(False)
            self.spin_http_timeout.setValue(120)
        except Exception:
            pass


