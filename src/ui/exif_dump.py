from __future__ import annotations

import os


def dump_exif_all(path: str) -> str:
    try:
        from PIL import Image, ExifTags  # type: ignore
    except Exception:
        return "Pillow가 설치되어 있지 않습니다."
    if Image is None or not os.path.exists(path):
        return ""
    try:
        name_map = getattr(__import__('PIL.ExifTags', fromlist=['TAGS']), 'TAGS', {})  # type: ignore
    except Exception:
        name_map = {}
    try:
        gps_name_map = getattr(__import__('PIL.ExifTags', fromlist=['GPSTAGS']), 'GPSTAGS', {})  # type: ignore
    except Exception:
        gps_name_map = {}

    def _val_to_str(v):
        try:
            if isinstance(v, bytes):
                try:
                    return v.decode('utf-8', errors='ignore')
                except Exception:
                    return repr(v)
            if isinstance(v, (list, tuple)):
                return ", ".join(_val_to_str(x) for x in v)
            return str(v)
        except Exception:
            return str(v)

    lines: list[str] = []
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            if not exif:
                try:
                    raw = im.info.get("exif")
                    if raw:
                        exif = Image.Exif()
                        exif.load(raw)
                except Exception:
                    pass
            if not exif:
                return "(EXIF 없음)"
            for tag_id, value in exif.items():
                tag_name = name_map.get(tag_id, f"Tag 0x{int(tag_id):04X}")
                if tag_name == 'GPSInfo' and isinstance(value, dict):
                    try:
                        gps_items = []
                        for k in value.keys():
                            sub_name = gps_name_map.get(k, f"0x{int(k):04X}")
                            gps_items.append((str(sub_name), _val_to_str(value[k])))
                        gps_items.sort(key=lambda x: x[0])
                        lines.append('[GPSInfo]')
                        for n, v in gps_items:
                            lines.append(f"GPS.{n}: {v}")
                    except Exception:
                        lines.append("[GPSInfo] <파싱 실패>")
                else:
                    try:
                        lines.append(f"{tag_name}: {_val_to_str(value)}")
                    except Exception:
                        lines.append(f"{tag_name}: <표시 실패>")
    except Exception:
        return "(EXIF 읽기 실패)"
    return "\n".join(lines)


