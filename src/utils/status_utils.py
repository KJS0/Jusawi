from PyQt6.QtGui import QImage, QColorSpace  # type: ignore[import]

def human_readable_size(size_bytes: int) -> str:
    try:
        b = float(size_bytes)
    except Exception:
        return "-"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    i = 0
    while b >= 1024.0 and i < len(units) - 1:
        b /= 1024.0
        i += 1
    if i == 0:
        return f"{int(b)} {units[i]}"
    return f"{b:.2f} {units[i]}"


def compute_display_bit_depth(img: QImage) -> int:
    try:
        fmt = img.format()
        if fmt in (QImage.Format.Format_RGB888, QImage.Format.Format_BGR888):
            return 24
        if fmt in (QImage.Format.Format_Grayscale8, QImage.Format.Format_Indexed8):
            return 8
        if fmt in (QImage.Format.Format_Mono, QImage.Format.Format_MonoLSB):
            return 1
        if fmt in (QImage.Format.Format_Grayscale16,):
            return 16
        if fmt in (QImage.Format.Format_RGBA64, QImage.Format.Format_RGBX64):
            return 64 if img.hasAlphaChannel() else 48
        d = img.depth()
        if d == 32 and not img.hasAlphaChannel():
            return 24
        return d
    except Exception:
        try:
            return img.depth()
        except Exception:
            return 0


def describe_colorspace(img: QImage) -> str:
    """간단한 색공간 설명 문자열(sRGB/기타/미상)."""
    try:
        cs = img.colorSpace()
        if not cs.isValid():
            return "unknown"
        try:
            if cs == QColorSpace(QColorSpace.NamedColorSpace.SRgb):
                return "sRGB"
        except Exception:
            pass
        # 기타인 경우 이름/primaries 정보가 있으면 간략화
        try:
            name = cs.description()
            if name:
                return name
        except Exception:
            pass
        return "non-sRGB"
    except Exception:
        return "unknown"


