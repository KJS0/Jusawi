from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QComboBox, QSpinBox, QFormLayout,
)

from .base import SettingsPage


class PerformanceSettingsPage(SettingsPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(8)
        except Exception:
            pass

        root.addWidget(QLabel("성능/프리페치", self))
        self.chk_prefetch_thumbs = QCheckBox("썸네일/이웃 이미지 프리로드", self)
        self.spin_preload_radius = QSpinBox(self); self.spin_preload_radius.setRange(0, 20); self.spin_preload_radius.setSuffix(" 장")
        self.chk_prefetch_map = QCheckBox("지도 캐시 프리페치", self)

        self.combo_preload_direction = QComboBox(self)
        self.combo_preload_direction.addItems(["양방향", "앞쪽", "뒤쪽"])  # both/forward/backward
        self.spin_preload_priority = QSpinBox(self); self.spin_preload_priority.setRange(-10, 10); self.spin_preload_priority.setSuffix(" prio")
        self.spin_preload_concurrency = QSpinBox(self); self.spin_preload_concurrency.setRange(0, 16); self.spin_preload_concurrency.setSuffix(" 개")
        self.spin_preload_retry = QSpinBox(self); self.spin_preload_retry.setRange(0, 5); self.spin_preload_retry.setSuffix(" 회")
        self.spin_preload_retry_delay = QSpinBox(self); self.spin_preload_retry_delay.setRange(0, 5000); self.spin_preload_retry_delay.setSuffix(" ms")

        self.spin_img_cache_mb = QSpinBox(self); self.spin_img_cache_mb.setRange(32, 4096); self.spin_img_cache_mb.setSuffix(" MB")
        self.spin_scaled_cache_mb = QSpinBox(self); self.spin_scaled_cache_mb.setRange(32, 8192); self.spin_scaled_cache_mb.setSuffix(" MB")
        self.spin_cache_auto_shrink_pct = QSpinBox(self); self.spin_cache_auto_shrink_pct.setRange(10, 90); self.spin_cache_auto_shrink_pct.setSuffix(" %")
        self.spin_cache_gc_interval = QSpinBox(self); self.spin_cache_gc_interval.setRange(0, 600); self.spin_cache_gc_interval.setSuffix(" s")

        self.spin_upgrade_delay = QSpinBox(self); self.spin_upgrade_delay.setRange(0, 300); self.spin_upgrade_delay.setSuffix(" ms")
        from PyQt6.QtWidgets import QDoubleSpinBox as _DSpin  # type: ignore
        self.dbl_preview_headroom = _DSpin(self); self.dbl_preview_headroom.setRange(1.0, 1.2); self.dbl_preview_headroom.setSingleStep(0.05); self.dbl_preview_headroom.setDecimals(2)
        self.chk_disable_scaled_below_100 = QCheckBox("100% 이하에서도 원본 우선(프리뷰 비활성화)", self)
        self.chk_preserve_visual_size_on_dpr = QCheckBox("DPI 변경 시 보이는 크기 유지", self)

        form_pf = QFormLayout()
        form_pf.addRow("썸네일 프리페치", self.chk_prefetch_thumbs)
        form_pf.addRow("이웃 프리로드 반경", self.spin_preload_radius)
        form_pf.addRow("지도 프리페치", self.chk_prefetch_map)
        form_pf.addRow("프리로드 방향", self.combo_preload_direction)
        form_pf.addRow("프리로드 우선순위", self.spin_preload_priority)
        form_pf.addRow("프리로드 동시 작업 수", self.spin_preload_concurrency)
        form_pf.addRow("프리로드 재시도 횟수", self.spin_preload_retry)
        form_pf.addRow("프리로드 재시도 지연", self.spin_preload_retry_delay)
        form_pf.addRow("업그레이드 지연", self.spin_upgrade_delay)
        form_pf.addRow("프리뷰 여유 배율", self.dbl_preview_headroom)
        form_pf.addRow("100% 이하 프리뷰 비활성화", self.chk_disable_scaled_below_100)
        form_pf.addRow("DPI 변경 시 크기 유지", self.chk_preserve_visual_size_on_dpr)
        form_pf.addRow("원본 캐시 상한", self.spin_img_cache_mb)
        form_pf.addRow("스케일 캐시 상한", self.spin_scaled_cache_mb)
        form_pf.addRow("저메모리 시 축소 비율", self.spin_cache_auto_shrink_pct)
        form_pf.addRow("캐시 정리 주기", self.spin_cache_gc_interval)
        root.addLayout(form_pf)

        # 썸네일 캐시
        root.addWidget(QLabel("썸네일 캐시", self))
        self.spin_thumb_quality = QSpinBox(self); self.spin_thumb_quality.setRange(50, 100); self.spin_thumb_quality.setSuffix(" %")
        from PyQt6.QtWidgets import QLineEdit as _QLineEdit  # type: ignore[import]
        self.ed_thumb_dir = _QLineEdit(self)
        self.ed_thumb_dir.setPlaceholderText("기본 경로 사용 시 비워두세요")
        from PyQt6.QtWidgets import QPushButton as _QPushButton, QFileDialog  # type: ignore[import]
        self.btn_thumb_dir = _QPushButton("변경…", self)
        def _pick_thumb_dir():
            try:
                d = QFileDialog.getExistingDirectory(self, "썸네일 캐시 폴더 선택", self.ed_thumb_dir.text() or "")
                if d:
                    self.ed_thumb_dir.setText(d)
            except Exception:
                pass
        try:
            self.btn_thumb_dir.clicked.connect(_pick_thumb_dir)
        except Exception:
            pass
        from PyQt6.QtWidgets import QHBoxLayout as _HBox  # type: ignore[import]
        _h = _HBox(); _h.addWidget(self.ed_thumb_dir, 1); _h.addWidget(self.btn_thumb_dir)
        row_thumb = QFormLayout()
        row_thumb.addRow("품질", self.spin_thumb_quality)
        row_thumb.addRow("저장 위치", _h)
        root.addLayout(row_thumb)

        # 지능형 스케일 프리젠
        root.addWidget(QLabel("지능형 스케일 프리젠", self))
        self.chk_pregen_scales = QCheckBox("선호 배율 미리 생성", self)
        from PyQt6.QtWidgets import QLineEdit as _QLineEdit2  # type: ignore[import]
        self.ed_pregen_scales = _QLineEdit2(self)
        self.ed_pregen_scales.setPlaceholderText("예: 0.25,0.5,1.0,2.0")
        form_pregen = QFormLayout()
        form_pregen.addRow("활성화", self.chk_pregen_scales)
        form_pregen.addRow("배율 목록", self.ed_pregen_scales)
        root.addLayout(form_pregen)

        # 프리로드 시점 옵션
        root.addWidget(QLabel("프리로드 시점", self))
        self.chk_preload_idle_only = QCheckBox("유휴 시간에만 프리로드 실행", self)
        self.spin_prefetch_on_dir_enter = QSpinBox(self); self.spin_prefetch_on_dir_enter.setRange(0, 50); self.spin_prefetch_on_dir_enter.setSuffix(" 장")
        self.spin_slideshow_prefetch = QSpinBox(self); self.spin_slideshow_prefetch.setRange(0, 100); self.spin_slideshow_prefetch.setSuffix(" 장")
        form_pt = QFormLayout()
        form_pt.addRow("유휴 시 프리로드", self.chk_preload_idle_only)
        form_pt.addRow("디렉터리 진입 예열", self.spin_prefetch_on_dir_enter)
        form_pt.addRow("슬라이드쇼 시작 예열", self.spin_slideshow_prefetch)
        root.addLayout(form_pt)

    def load_from_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            self.chk_prefetch_thumbs.setChecked(bool(getattr(viewer, "_enable_thumb_prefetch", True)))
        except Exception:
            self.chk_prefetch_thumbs.setChecked(True)
        try:
            self.spin_preload_radius.setValue(int(getattr(viewer, "_preload_radius", 2)))
        except Exception:
            self.spin_preload_radius.setValue(2)
        try:
            self.chk_prefetch_map.setChecked(bool(getattr(viewer, "_enable_map_prefetch", True)))
        except Exception:
            self.chk_prefetch_map.setChecked(True)
        try:
            dir_map = {"both":0, "forward":1, "backward":2}
            self.combo_preload_direction.setCurrentIndex(dir_map.get(str(getattr(viewer, "_preload_direction", "both")), 0))
        except Exception:
            self.combo_preload_direction.setCurrentIndex(0)
        try:
            self.spin_preload_priority.setValue(int(getattr(viewer, "_preload_priority", -1)))
        except Exception:
            self.spin_preload_priority.setValue(-1)
        try:
            self.spin_preload_concurrency.setValue(int(getattr(viewer, "_preload_max_concurrency", 0)))
        except Exception:
            self.spin_preload_concurrency.setValue(0)
        try:
            self.spin_preload_retry.setValue(int(getattr(viewer, "_preload_retry_count", 0)))
        except Exception:
            self.spin_preload_retry.setValue(0)
        try:
            self.spin_preload_retry_delay.setValue(int(getattr(viewer, "_preload_retry_delay_ms", 0)))
        except Exception:
            self.spin_preload_retry_delay.setValue(0)
        try:
            self.spin_upgrade_delay.setValue(int(getattr(viewer, "_fullres_upgrade_delay_ms", 120)))
        except Exception:
            self.spin_upgrade_delay.setValue(120)
        try:
            self.dbl_preview_headroom.setValue(float(getattr(viewer, "_preview_headroom", 1.0)))
        except Exception:
            self.dbl_preview_headroom.setValue(1.0)
        try:
            self.chk_disable_scaled_below_100.setChecked(bool(getattr(viewer, "_disable_scaled_cache_below_100", False)))
        except Exception:
            self.chk_disable_scaled_below_100.setChecked(False)
        try:
            self.chk_preserve_visual_size_on_dpr.setChecked(bool(getattr(viewer, "_preserve_visual_size_on_dpr_change", False)))
        except Exception:
            self.chk_preserve_visual_size_on_dpr.setChecked(False)
        try:
            mb = int(max(1, int(getattr(viewer, "_img_cache_max_bytes", 256*1024*1024)) // (1024*1024)))
            self.spin_img_cache_mb.setValue(mb)
        except Exception:
            self.spin_img_cache_mb.setValue(256)
        try:
            mb2 = int(max(1, int(getattr(viewer, "_scaled_cache_max_bytes", 384*1024*1024)) // (1024*1024)))
            self.spin_scaled_cache_mb.setValue(mb2)
        except Exception:
            self.spin_scaled_cache_mb.setValue(384)
        try:
            self.spin_cache_auto_shrink_pct.setValue(int(getattr(viewer, "_cache_auto_shrink_pct", 50)))
        except Exception:
            self.spin_cache_auto_shrink_pct.setValue(50)
        try:
            self.spin_cache_gc_interval.setValue(int(getattr(viewer, "_cache_gc_interval_s", 0)))
        except Exception:
            self.spin_cache_gc_interval.setValue(0)
        try:
            self.spin_thumb_quality.setValue(int(getattr(viewer, "_thumb_cache_quality", 85)))
        except Exception:
            self.spin_thumb_quality.setValue(85)
        try:
            self.ed_thumb_dir.setText(str(getattr(viewer, "_thumb_cache_dir", "")) or "")
        except Exception:
            self.ed_thumb_dir.setText("")
        try:
            self.chk_pregen_scales.setChecked(bool(getattr(viewer, "_pregen_scales_enabled", False)))
        except Exception:
            self.chk_pregen_scales.setChecked(False)
        try:
            arr = getattr(viewer, "_pregen_scales", [0.25, 0.5, 1.0, 2.0])
            if isinstance(arr, (list, tuple)):
                txt = ",".join([str(x) for x in arr])
            else:
                txt = "0.25,0.5,1.0,2.0"
            self.ed_pregen_scales.setText(txt)
        except Exception:
            self.ed_pregen_scales.setText("0.25,0.5,1.0,2.0")
        try:
            self.chk_preload_idle_only.setChecked(bool(getattr(viewer, "_preload_only_when_idle", False)))
        except Exception:
            self.chk_preload_idle_only.setChecked(False)
        try:
            self.spin_prefetch_on_dir_enter.setValue(int(getattr(viewer, "_prefetch_on_dir_enter", 0)))
        except Exception:
            self.spin_prefetch_on_dir_enter.setValue(0)
        try:
            self.spin_slideshow_prefetch.setValue(int(getattr(viewer, "_slideshow_prefetch_count", 0)))
        except Exception:
            self.spin_slideshow_prefetch.setValue(0)

    def apply_to_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        try:
            viewer._enable_thumb_prefetch = bool(self.chk_prefetch_thumbs.isChecked())
        except Exception:
            pass
        try:
            viewer._preload_radius = int(self.spin_preload_radius.value())
        except Exception:
            pass
        try:
            viewer._enable_map_prefetch = bool(self.chk_prefetch_map.isChecked())
        except Exception:
            pass
        try:
            idx = int(self.combo_preload_direction.currentIndex())
            viewer._preload_direction = ("both" if idx == 0 else ("forward" if idx == 1 else "backward"))
        except Exception:
            pass
        try:
            viewer._preload_priority = int(self.spin_preload_priority.value())
        except Exception:
            pass
        try:
            viewer._preload_max_concurrency = int(self.spin_preload_concurrency.value())
        except Exception:
            pass
        try:
            viewer._preload_retry_count = int(self.spin_preload_retry.value())
        except Exception:
            pass
        try:
            viewer._preload_retry_delay_ms = int(self.spin_preload_retry_delay.value())
        except Exception:
            pass
        try:
            viewer._fullres_upgrade_delay_ms = int(self.spin_upgrade_delay.value())
        except Exception:
            pass
        try:
            viewer._preview_headroom = float(self.dbl_preview_headroom.value())
        except Exception:
            pass
        try:
            viewer._disable_scaled_cache_below_100 = bool(self.chk_disable_scaled_below_100.isChecked())
        except Exception:
            pass
        try:
            viewer._preserve_visual_size_on_dpr_change = bool(self.chk_preserve_visual_size_on_dpr.isChecked())
        except Exception:
            pass
        try:
            viewer._img_cache_max_bytes = int(self.spin_img_cache_mb.value()) * 1024 * 1024
            viewer._scaled_cache_max_bytes = int(self.spin_scaled_cache_mb.value()) * 1024 * 1024
            if hasattr(viewer, "image_service") and viewer.image_service is not None:
                viewer.image_service.set_cache_limits(viewer._img_cache_max_bytes, viewer._scaled_cache_max_bytes)
        except Exception:
            pass
        try:
            viewer._cache_auto_shrink_pct = int(self.spin_cache_auto_shrink_pct.value())
            viewer._cache_gc_interval_s = int(self.spin_cache_gc_interval.value())
        except Exception:
            pass
        try:
            viewer._thumb_cache_quality = int(self.spin_thumb_quality.value())
            viewer._thumb_cache_dir = str(self.ed_thumb_dir.text()).strip()
        except Exception:
            pass
        try:
            viewer._pregen_scales_enabled = bool(self.chk_pregen_scales.isChecked())
            raw = str(self.ed_pregen_scales.text()).strip()
            arr = []
            for p in [t.strip() for t in raw.split(',') if t.strip()]:
                try:
                    arr.append(float(p))
                except Exception:
                    pass
            if not arr:
                arr = [0.25, 0.5, 1.0, 2.0]
            viewer._pregen_scales = arr
        except Exception:
            pass
        try:
            viewer._preload_only_when_idle = bool(self.chk_preload_idle_only.isChecked())
        except Exception:
            pass
        try:
            viewer._prefetch_on_dir_enter = int(self.spin_prefetch_on_dir_enter.value())
        except Exception:
            pass
        try:
            viewer._slideshow_prefetch_count = int(self.spin_slideshow_prefetch.value())
        except Exception:
            pass

    def reset_to_defaults(self) -> None:
        try:
            self.chk_prefetch_thumbs.setChecked(True)
            self.spin_preload_radius.setValue(2)
            self.chk_prefetch_map.setChecked(True)
            self.combo_preload_direction.setCurrentIndex(0)
            self.spin_preload_priority.setValue(-1)
            self.spin_preload_concurrency.setValue(0)
            self.spin_preload_retry.setValue(0)
            self.spin_preload_retry_delay.setValue(0)
            self.spin_upgrade_delay.setValue(120)
            self.dbl_preview_headroom.setValue(1.0)
            self.chk_disable_scaled_below_100.setChecked(False)
            self.chk_preserve_visual_size_on_dpr.setChecked(False)
            self.spin_img_cache_mb.setValue(256)
            self.spin_scaled_cache_mb.setValue(384)
            self.spin_cache_auto_shrink_pct.setValue(50)
            self.spin_cache_gc_interval.setValue(0)
            self.spin_thumb_quality.setValue(85)
            self.ed_thumb_dir.setText("")
            self.chk_pregen_scales.setChecked(False)
            self.ed_pregen_scales.setText("0.25,0.5,1.0,2.0")
            self.chk_preload_idle_only.setChecked(False)
            self.spin_prefetch_on_dir_enter.setValue(0)
            self.spin_slideshow_prefetch.setValue(0)
        except Exception:
            pass


