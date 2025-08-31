import io
import os
from dataclasses import dataclass
from typing import Optional, Tuple


try:
    from PIL import Image, ImageCms, PngImagePlugin
except Exception:  # pragma: no cover - Pillow optional in some environments
    Image = None  # type: ignore
    ImageCms = None  # type: ignore
    PngImagePlugin = None  # type: ignore


EXIF_ORIENTATION_TAG = 274


@dataclass
class ImageMetadata:
    exif_bytes: Optional[bytes] = None
    icc_profile: Optional[bytes] = None
    xmp_bytes: Optional[bytes] = None


def extract_metadata(image_path: str) -> ImageMetadata:
    if Image is None or not os.path.exists(image_path):
        return ImageMetadata()
    try:
        with Image.open(image_path) as im:
            exif_bytes = None
            try:
                exif = im.getexif()
                if exif:  # may be empty dict-like
                    exif_bytes = exif.tobytes()
            except Exception:
                exif_bytes = None
            icc_profile = None
            try:
                icc_profile = im.info.get("icc_profile")
            except Exception:
                icc_profile = None
            xmp_bytes = None
            try:
                # Pillow exposes XMP sometimes as 'XML:com.adobe.xmp' or 'xmp'
                xmp_bytes = im.info.get("XML:com.adobe.xmp") or im.info.get("xmp")
            except Exception:
                xmp_bytes = None
            return ImageMetadata(exif_bytes=exif_bytes, icc_profile=icc_profile, xmp_bytes=xmp_bytes)
    except Exception:
        return ImageMetadata()


def normalize_orientation_in_exif(exif_bytes: Optional[bytes]) -> Optional[bytes]:
    if Image is None or not exif_bytes:
        return exif_bytes
    try:
        exif = Image.Exif()
        try:
            exif.load(exif_bytes)
        except Exception:
            # Fallback: create new EXIF container
            exif = Image.Exif()
        # Orientation을 1로 고정
        exif[EXIF_ORIENTATION_TAG] = 1
        return exif.tobytes()
    except Exception:
        return exif_bytes


def encode_with_metadata(pil_image, dest_format: str, quality: int, meta: ImageMetadata) -> Tuple[bool, bytes, str]:
    """
    pil_image: PIL.Image.Image (RGB/RGBA)
    dest_format: 'JPEG' | 'PNG' | 'TIFF' | ...
    quality: 1..100 (JPEG 등)
    meta: 보존할 메타데이터
    반환: (성공, 바이트, 오류)
    """
    if Image is None:
        return False, b"", "Pillow가 설치되어 있지 않습니다."
    try:
        params = {}
        fmt = (dest_format or "").upper()
        # EXIF Orientation 정규화
        exif_bytes = normalize_orientation_in_exif(meta.exif_bytes)
        if fmt == "JPEG":
            params["quality"] = int(quality)
            params["subsampling"] = 0
            params["optimize"] = True
            if exif_bytes:
                params["exif"] = exif_bytes
            if meta.icc_profile:
                params["icc_profile"] = meta.icc_profile
        elif fmt == "PNG":
            # PNG에서도 EXIF가 지원됨(Pillow>=7). ICC도 지원.
            if exif_bytes:
                params["exif"] = exif_bytes
            if meta.icc_profile:
                params["icc_profile"] = meta.icc_profile
            # XMP는 표준화 덜 되었지만 텍스트 청크로 보존 시도
            if meta.xmp_bytes and PngImagePlugin is not None:
                pnginfo = PngImagePlugin.PngInfo()
                try:
                    pnginfo.add_text("XML:com.adobe.xmp", meta.xmp_bytes.decode("utf-8", errors="ignore"))
                    params["pnginfo"] = pnginfo
                except Exception:
                    pass
        else:
            # 기타 포맷: 가능한 항목만 적용
            if exif_bytes:
                params["exif"] = exif_bytes
            if meta.icc_profile:
                params["icc_profile"] = meta.icc_profile

        buf = io.BytesIO()
        pil_image.save(buf, format=fmt if fmt else None, **params)
        return True, buf.getvalue(), ""
    except Exception as e:
        return False, b"", str(e)


