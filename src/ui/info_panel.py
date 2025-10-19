from __future__ import annotations

import os
from typing import Optional, Tuple

# PyQt imports are type-ignored to avoid hard deps at import time
from PyQt6.QtCore import QTimer  # type: ignore[import]
from PyQt6.QtGui import QPixmap  # type: ignore[import]
from PyQt6.QtWidgets import QTextEdit, QLabel  # type: ignore[import]


def setup_info_panel(owner) -> None:
    """Initialize info panel related timers, tokens, and connect signals on owner.

    Owner is expected to be the main window instance providing:
    - _kick_map_fetch(), _on_map_ready()
    - attributes: _map_req_token, _map_debounce, _map_emitter
    - widgets: info_text, info_map_label
    """
    # debounce/token
    owner._map_req_token = 0
    owner._map_debounce = QTimer(owner)
    owner._map_debounce.setSingleShot(True)
    owner._map_debounce.setInterval(300)
    owner._map_debounce.timeout.connect(owner._kick_map_fetch)

    # simple emitter object with Qt signal for map readiness
    from PyQt6.QtCore import QObject, pyqtSignal  # type: ignore[import]

    class _MapEmitter(QObject):
        ready = pyqtSignal(int, QPixmap)

    owner._map_emitter = _MapEmitter(owner)
    try:
        owner._map_emitter.ready.connect(owner._on_map_ready)
    except Exception:
        pass


def toggle_info_panel(owner) -> None:
    try:
        target = getattr(owner, "info_tabs", None) or getattr(owner, "info_text", None)
        visible = not bool(target.isVisible()) if target is not None else True
    except Exception:
        visible = True
    try:
        if getattr(owner, "info_panel", None) is not None:
            owner.info_panel.setVisible(visible)
    except Exception:
        pass
    if visible:
        try:
            update_info_panel(owner)
        except Exception:
            pass


def format_bytes(num_bytes: int) -> str:
    try:
        n = float(num_bytes)
    except Exception:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024.0 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    if i == 0:
        return f"{int(n)} {units[i]}"
    return f"{n:.2f} {units[i]}"


def _safe_frac_to_float(v):
    try:
        if hasattr(v, "numerator") and hasattr(v, "denominator"):
            num = float(getattr(v, "numerator"))
            den = float(getattr(v, "denominator"))
            if den == 0:
                return None
            return num / den
        if isinstance(v, (tuple, list)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
            if float(v[1]) == 0:
                return None
            return float(v[0]) / float(v[1])
        s = str(v)
        if "/" in s:
            a, b = s.split("/", 1)
            fa, fb = float(a), float(b)
            if fb != 0:
                return fa / fb
        return float(s)
    except Exception:
        return None


def update_info_panel(owner) -> None:
    path = owner.current_image_path or ""
    if not path or not os.path.exists(path):
        try:
            if getattr(owner, "info_text", None) is not None:
                owner.info_text.setPlainText("")
            if getattr(owner, "info_map_label", None) is not None:
                owner.info_map_label.setText("여기에 지도가 표시됩니다.")
        except Exception:
            pass
        return

    file_name = os.path.basename(path)
    dir_name = os.path.dirname(path)
    try:
        size_bytes = os.path.getsize(path)
    except Exception:
        size_bytes = 0

    try:
        w = int(getattr(owner, "_fullres_image", None).width()) if getattr(owner, "_fullres_image", None) is not None else 0
        h = int(getattr(owner, "_fullres_image", None).height()) if getattr(owner, "_fullres_image", None) is not None else 0
        if w <= 0 or h <= 0:
            px = owner.image_display_area.originalPixmap()
            if px is not None and not px.isNull():
                w = int(px.width())
                h = int(px.height())
    except Exception:
        w = h = 0

    mp_text = "-"
    try:
        if w > 0 and h > 0:
            mp = (w * h) / 1_000_000.0
            mp_text = f"{mp:.1f}MP"
    except Exception:
        pass

    summary_text = ""
    try:
        from ..services.exif_utils import extract_with_pillow, format_summary_text  # type: ignore
        exif_raw = extract_with_pillow(path) or {}
        summary_text = format_summary_text(exif_raw, path)
    except Exception:
        summary_text = ""

    exposure_bias_ev = None
    try:
        from PIL import Image, ExifTags  # type: ignore
        if Image is not None:
            with Image.open(path) as im:
                ev_exif = im.getexif()
                name_map = getattr(ExifTags, 'TAGS', {})
                for tag_id, val in (ev_exif.items() if ev_exif else []):
                    name = name_map.get(tag_id, str(tag_id))
                    if name == 'ExposureBiasValue':
                        fv = _safe_frac_to_float(val)
                        if fv is not None:
                            exposure_bias_ev = fv
                            break
    except Exception:
        exposure_bias_ev = None

    address_text = None
    try:
        lat = exif_raw.get("lat") if isinstance(exif_raw, dict) else None  # type: ignore[name-defined]
        lon = exif_raw.get("lon") if isinstance(exif_raw, dict) else None  # type: ignore[name-defined]
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            try:
                from ..services.geocoding import geocoding_service  # type: ignore
                addr = geocoding_service.get_address_from_coordinates(float(lat), float(lon))
                if addr and isinstance(addr, dict):
                    address_text = str(addr.get("formatted") or addr.get("full_address") or "")
            except Exception:
                address_text = None
        if getattr(owner, "info_map_label", None) is not None:
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and owner.info_panel.isVisible():
                try:
                    owner.info_map_label.setVisible(True)
                except Exception:
                    pass
                schedule_map_fetch(owner, float(lat), float(lon), 600, 360, 12)
            else:
                try:
                    owner.info_map_label.setVisible(False)
                except Exception:
                    pass
    except Exception:
        try:
            if getattr(owner, "info_map_label", None) is not None:
                owner.info_map_label.setVisible(False)
        except Exception:
            pass

        if not summary_text:
            lines = []
            dt = "-"
            lines.append(f"촬영 날짜 및 시간: {dt}")
            lines.append(f"파일명: {file_name}")
            lines.append(f"디렉토리명: {dir_name}")
            # 촬영 기기/초점거리/ISO/조리개/셔터속도는 값이 없을 때 공란으로 표시
            lines.append("촬영 기기: ")
            res = f"{w} x {h}" if w > 0 and h > 0 else "-"
            # 용량 | 해상도 | 화소 한 줄로 표시
            lines.append(f"용량: {format_bytes(size_bytes)} | 해상도: {res} | 화소수: {mp_text}")
            lines.append("ISO: ")
            lines.append("초점 거리: ")
            lines.append("노출도: ")
            lines.append("조리개값: ")
            lines.append("셔터속도: ")
            lines.append("GPS 위도, 경도: -")
            summary_text = "\n".join(lines)

    try:
        if address_text:
            lines = (summary_text or "").splitlines()
            inserted = False
            for i, line in enumerate(lines):
                if line.strip().startswith("GPS 위도, 경도:"):
                    lines.insert(i + 1, f"주소 : {address_text}")
                    inserted = True
                    break
            if not inserted and summary_text:
                lines.append(f"{address_text}")
            if lines:
                summary_text = "\n".join(lines)
    except Exception:
        pass

    try:
        if getattr(owner, "info_text", None) is not None:
            owner.info_text.setPlainText(summary_text)
    except Exception:
        pass


def schedule_map_fetch(owner, lat: float, lon: float, w: int, h: int, zoom: int) -> None:
    owner._pending_map = (lat, lon, w, h, zoom)
    try:
        owner._map_debounce.start()
    except Exception:
        kick_map_fetch(owner)


def kick_map_fetch(owner) -> None:
    if not hasattr(owner, "_pending_map"):
        return
    lat, lon, w, h, zoom = owner._pending_map
    owner._map_req_token += 1
    token = int(owner._map_req_token)
    try:
        from ..services.map_cache import submit_fetch  # type: ignore
        submit_fetch(lat, lon, int(w), int(h), int(zoom), token, owner._map_emitter, "ready")
    except Exception:
        pass


def on_map_ready(owner, token: int, pm) -> None:
    if token != getattr(owner, "_map_req_token", 0):
        return
    if getattr(owner, "info_map_label", None) is None:
        return
    try:
        if pm is not None and not pm.isNull():
            owner.info_map_label.setPixmap(pm)
            owner.info_map_label.setVisible(True)
        else:
            owner.info_map_label.setVisible(False)
    except Exception:
        pass


def update_info_panel_sizes(owner) -> None:
    try:
        # 스플리터 롤백: 정보 패널 폭을 고정(창 너비 비례)하여 이미지 영역이 지나치게 줄지 않도록 함
        total_w = max(640, int(owner.width()))
        panel_w = max(360, int(total_w * 0.42))
        panel_h = int(panel_w * 0.61)
        if getattr(owner, "info_map_label", None) is not None:
            try:
                owner.info_map_label.setFixedSize(panel_w, panel_h)
            except Exception:
                pass
        if getattr(owner, "info_text", None) is not None:
            try:
                scaled = max(16, min(24, int(total_w / 80)))
                owner.info_text.setFixedWidth(panel_w)
                owner.info_text.setStyleSheet(f"QTextEdit {{ color: #EAEAEA; background-color: #2B2B2B; border: 1px solid #444; font-size: {scaled}px; line-height: 140%; }}")
            except Exception:
                pass
        if getattr(owner, "info_panel", None) is not None:
            try:
                owner.info_panel.setFixedWidth(panel_w)
            except Exception:
                pass
    except Exception:
        pass


