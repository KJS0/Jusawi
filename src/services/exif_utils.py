from __future__ import annotations

import os
from typing import Any, Dict

try:
    from PIL import Image, ExifTags  # type: ignore
    try:
        from PIL.ExifTags import TAGS as _PIL_TAGS, GPSTAGS as _PIL_GPSTAGS  # type: ignore
    except Exception:
        _PIL_TAGS, _PIL_GPSTAGS = {}, {}
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ExifTags = None  # type: ignore
    _PIL_TAGS, _PIL_GPSTAGS = {}, {}


def _to_float(value: Any) -> float | None:
    try:
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            num = float(getattr(value, "numerator"))
            den = float(getattr(value, "denominator"))
            if den == 0:
                return None
            return num / den
        if isinstance(value, (tuple, list)) and len(value) == 2 and all(isinstance(x, (int, float)) for x in value):
            if float(value[1]) == 0:
                return None
            return float(value[0]) / float(value[1])
        s = str(value)
        if "/" in s:
            a, b = s.split("/", 1)
            fa, fb = float(a), float(b)
            if fb == 0:
                return None
            return fa / fb
        return float(s)
    except Exception:
        return None


def _format_ev(x: float | None) -> str | None:
    if x is None:
        return None
    return f"{x:+.1f}EV"


def _format_shutter(seconds: float | None) -> str | None:
    if seconds is None or seconds <= 0:
        return None
    if seconds < 1.0:
        den = max(1, round(1.0 / seconds))
        return f"1/{den}s"
    if abs(seconds - round(seconds)) < 1e-3:
        return f"{int(round(seconds))}s"
    return f"{seconds:.1f}s"


def _format_fnumber(f: float | None) -> str | None:
    if f is None:
        return None
    return f"F{f:.1f}"


def _dms_to_deg(dms, ref) -> float | None:
    try:
        if not dms:
            return None
        d = _to_float(dms[0])
        m = _to_float(dms[1])
        s = _to_float(dms[2])
        if None in (d, m, s):
            return None
        sign = -1 if str(ref).upper() in ("S", "W") else 1
        return sign * (d + m / 60.0 + s / 3600.0)
    except Exception:
        return None


def _human_bytes(n: int) -> str:
    try:
        size = float(n)
    except Exception:
        return "-"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0 or unit == "TB":
            return f"{int(size)}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024.0
    return "-"


def extract_with_pillow(path: str) -> Dict[str, Any]:
    """표준 EXIF 명칭 기반으로 안전하게 값 추출.
    실패 시 가능한 한 None/결측으로 반환.
    """
    if Image is None or not os.path.exists(path):
        return {}
    try:
        with Image.open(path) as im:
            width, height = im.size
            # 원시 EXIF: _getexif() 우선, 폴백 getexif()/info['exif']
            ex = None
            try:
                ex = getattr(im, "_getexif", lambda: None)() or None
            except Exception:
                ex = None
            if not ex:
                ex = im.getexif() or {}
                if not ex:
                    try:
                        raw = im.info.get("exif")
                        if raw:
                            ex2 = Image.Exif()
                            ex2.load(raw)
                            ex = ex2
                    except Exception:
                        pass
            # 명칭 매핑
            name_map = _PIL_TAGS or (getattr(ExifTags, 'TAGS', {}) if ExifTags else {})
            exif_named = {name_map.get(k, k): v for k, v in (ex.items() if hasattr(ex, 'items') else [])}

            # 기본 항목
            dt = exif_named.get("DateTimeOriginal") or exif_named.get("DateTime")
            make = exif_named.get("Make")
            model = exif_named.get("Model")
            fnumber = _to_float(exif_named.get("FNumber"))
            exposure_time = _to_float(exif_named.get("ExposureTime"))
            ev = _to_float(exif_named.get("ExposureBiasValue"))
            # ISO 다중 태그
            def _get_iso_value(ex_named: Dict[str, Any]) -> str | None:
                for tag in ("ISO", "ISOSpeedRatings", "PhotographicSensitivity"):
                    if tag in ex_named:
                        val = ex_named[tag]
                        if hasattr(val, 'numerator') and hasattr(val, 'denominator') and getattr(val, 'denominator') != 0:
                            return str(int(val.numerator / val.denominator))
                        if isinstance(val, (int, float)):
                            return str(int(val))
                        if isinstance(val, (tuple, list)) and len(val) >= 1:
                            try:
                                return str(int(val[0]))
                            except Exception:
                                continue
                        try:
                            s = str(val).strip()
                            if s.isdigit():
                                return s
                        except Exception:
                            pass
                return None
            iso_str = _get_iso_value(exif_named)
            iso_val = None
            try:
                iso_val = int(iso_str) if iso_str and str(iso_str).isdigit() else None
            except Exception:
                iso_val = None
            focal = _to_float(exif_named.get("FocalLength"))
            focal35 = exif_named.get("FocalLengthIn35mmFilm")
            # 조리개 텍스트: FNumber 우선, 없으면 ApertureValue(APEX)
            def _format_aperture_from_named(ex_named: Dict[str, Any]) -> str | None:
                val = ex_named.get("FNumber")
                fv = _to_float(val)
                if fv and fv > 0:
                    return f"f/{fv:.1f}"
                av = ex_named.get("ApertureValue")
                avf = _to_float(av)
                if avf is not None:
                    try:
                        n = 2.0 ** (float(avf) / 2.0)
                        if n > 0:
                            return f"f/{n:.1f}"
                    except Exception:
                        pass
                return None
            aperture_text = _format_aperture_from_named(exif_named)
            # 셔터 텍스트: ExposureTime 우선, 없으면 ShutterSpeedValue(APEX)
            def _format_shutter_from_named(ex_named: Dict[str, Any]) -> str | None:
                et = _to_float(ex_named.get("ExposureTime"))
                if et and et > 0:
                    return _format_shutter(et)
                tv = _to_float(ex_named.get("ShutterSpeedValue"))
                if tv is not None:
                    try:
                        secs = 2.0 ** (-float(tv))
                        return _format_shutter(secs)
                    except Exception:
                        pass
                return None
            shutter_text = _format_shutter_from_named(exif_named)
            # GPS
            lat = lon = None
            gps = exif_named.get("GPSInfo")
            if isinstance(gps, dict):
                GPS_TAGS = _PIL_GPSTAGS or getattr(__import__('PIL.ExifTags', fromlist=['GPSTAGS']), 'GPSTAGS', {})
                gps_named = {GPS_TAGS.get(k, k): v for k, v in gps.items()}
                lat = _dms_to_deg(gps_named.get("GPSLatitude"), gps_named.get("GPSLatitudeRef"))
                lon = _dms_to_deg(gps_named.get("GPSLongitude"), gps_named.get("GPSLongitudeRef"))
        mp = None
        try:
            mp = round((width * height) / 1_000_000)
        except Exception:
            mp = None
        out = {
            "datetime": dt,
            "make": make,
            "model": model,
            "fnumber": fnumber,
            "exposure_time": exposure_time,
            "aperture_text": aperture_text,
            "shutter_text": shutter_text,
            "ev": ev,
            "iso": iso_val if iso_val is not None else iso_str,
            "focal_mm": focal,
            "focal_35mm": focal35,
            "lat": lat,
            "lon": lon,
            "width": width,
            "height": height,
            "megapixels": mp,
        }
        return out
    except Exception:
        return {}


def format_summary_text(meta: Dict[str, Any], path: str) -> str:
    try:
        # 디렉토리 경로 전체(최상위부터)를 역슬래시로 표시
        full_dir = os.path.dirname(path)
        filename = os.path.basename(path)
        try:
            file_bytes = os.path.getsize(path)
        except Exception:
            file_bytes = 0
        parts = []
        parts.append(f"{meta.get('datetime') or '-'}")
        make = str(meta.get('make') or '').strip()
        model = str(meta.get('model') or '').strip()
        cam = " ".join([x for x in [make, model] if x]) or "-"
        parts.append(f"{full_dir}/{filename}")
        parts.append(f"{_human_bytes(file_bytes)}")
        w, h = meta.get('width') or 0, meta.get('height') or 0
        parts.append(f"{w} x {h}" if w and h else "-")
        mp = meta.get('megapixels')
        parts.append(f"{mp}MP" if mp else "-")
        iso = meta.get('iso')
        parts.append(f"{cam}")
        fl = meta.get('focal_mm')
        fl35 = meta.get('focal_35mm')
        if fl and fl35:
            parts.append(f"{int(round(fl))}mm (환산 {int(round(float(fl35)))}mm)")
        elif fl35:
            parts.append(f"환산 {int(round(float(fl35)))}mm")
        elif fl:
            parts.append(f"{int(round(fl))}mm")
        else:
            parts.append("-")
        fn = _format_fnumber(meta.get('fnumber')) or "-"
        sh = _format_shutter(meta.get('exposure_time')) or "-"
        iso = meta.get('iso') or "-"
        parts.append(f"{sh} | {fn} | {iso}")
        lat, lon = meta.get('lat'), meta.get('lon')
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            parts.append(f"{lat:.6f}, {lon:.6f}")
        else:
            parts.append("")
        return "\n".join(parts)
    except Exception:
        return ""


