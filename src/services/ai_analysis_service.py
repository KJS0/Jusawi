from __future__ import annotations

import os
import io
import json
import base64
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    from PIL import Image, ImageCms  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ImageCms = None  # type: ignore

# 프록시/외부 HTTP 클라이언트 사용 안 함

from ..utils.logging_setup import get_logger

_log = get_logger("svc.AIAnalysis")


SCHEMA_DEFAULT: Dict[str, Any] = {
    "short_caption": "",
    "long_caption": "",
    "tags": [],
    "subjects": [],
    "shooting_intent": None,
    "camera_settings": {
        "aperture": None,
        "shutter": None,
        "iso": None,
        "focal_length_mm": None,
        "focal_length_35mm_eq_mm": None,
    },
    "gps": {"lat": None, "lon": None, "place_guess": None},
    "safety": {"nsfw": False, "sensitive": []},
    "confidence": 0.0,
    "notes": "",
}


@dataclass
class AnalysisContext:
    purpose: str = "archive"  # blog | archive | sns
    tone: str = "중립"
    language: str = "ko"
    long_caption_chars: int = 120  # 80~160 권장
    short_caption_words: int = 16  # 12~18 권장
    prompt_version: str = "20250907_1"
    user_keywords: Optional[str] = None
    # OpenAI Vision detail level: "low" | "high" | "auto"
    detail: str = "auto"


def _extract_exif_summary(image_path: str) -> Dict[str, Any]:
    """Pillow로 가벼운 EXIF 요약을 추출한다. 실패 시 빈 값으로 반환."""
    if Image is None or not os.path.exists(image_path):
        return {}
    try:
        from PIL import ExifTags  # type: ignore
    except Exception:
        return {}
    try:
        with Image.open(image_path) as im:
            exif_map: Dict[str, Any] = {}
            gps_map: Dict[str, Any] = {}
            try:
                exif = im.getexif()
                if exif:
                    for tag_id, value in exif.items():
                        name = getattr(ExifTags, 'TAGS', {}).get(tag_id, str(tag_id))
                        if name == 'GPSInfo' and isinstance(value, dict):
                            try:
                                from PIL.ExifTags import GPSTAGS  # type: ignore
                                gps_map = {GPSTAGS.get(k, str(k)): value[k] for k in value.keys()}
                            except Exception:
                                gps_map = {str(k): value[k] for k in value.keys()}
                            continue
                        exif_map[name] = value
            except Exception:
                pass
            # 우리가 필요로 하는 핵심 키만 매핑
            def _frac_to_str(v: Any) -> str | None:
                try:
                    s = str(v)
                    if "/" in s:
                        a, b = s.split("/", 1)
                        fa, fb = float(a), float(b)
                        if fb != 0:
                            if fa > fb:
                                return f"{fa/fb:.4f}"
                            return f"{int(fa)}/{int(fb)}"
                    return s
                except Exception:
                    return None

            out: Dict[str, Any] = {
                "make": str(exif_map.get("Make", "")) or None,
                "model": str(exif_map.get("Model", "")) or None,
                "lens": str(exif_map.get("LensModel", "")) or None,
                "aperture": None,
                "shutter": None,
                "iso": None,
                "focal_length_mm": None,
                "focal_length_35mm_eq_mm": None,
                "datetime_original": str(exif_map.get("DateTimeOriginal", exif_map.get("DateTime", ""))) or None,
                "gps": {"lat": None, "lon": None},
            }
            # Aperture (FNumber)
            try:
                fnum = exif_map.get("FNumber")
                if fnum is not None:
                    fs = _frac_to_str(fnum)
                    if fs is not None:
                        out["aperture"] = f"f/{float(fs):.1f}" if "/" not in fs else f"f/{float(fs.split('/') [0]) / float(fs.split('/') [1]):.1f}"
            except Exception:
                pass
            # ExposureTime
            try:
                et = exif_map.get("ExposureTime")
                if et is not None:
                    ets = _frac_to_str(et)
                    if ets:
                        out["shutter"] = ets + ("s" if not ets.endswith("s") and "/" not in ets else "")
            except Exception:
                pass
            # ISO
            try:
                iso = exif_map.get("ISOSpeedRatings", exif_map.get("PhotographicSensitivity"))
                if iso is not None:
                    out["iso"] = int(str(iso).split()[0])
            except Exception:
                pass
            # Focal lengths
            try:
                fl = exif_map.get("FocalLength")
                if fl is not None:
                    s = _frac_to_str(fl)
                    if s:
                        if "/" in s:
                            num, den = s.split("/", 1)
                            out["focal_length_mm"] = int(round(float(num) / float(den)))
                        elif s.replace('.', '', 1).isdigit():
                            out["focal_length_mm"] = int(round(float(s)))
            except Exception:
                pass
            try:
                fleq = exif_map.get("FocalLengthIn35mmFilm")
                if fleq is not None:
                    out["focal_length_35mm_eq_mm"] = int(str(fleq).split()[0])
            except Exception:
                pass
            # GPS
            try:
                def _to_deg(x):
                    try:
                        num, den = float(x[0]), float(x[1])
                        return num / den if den != 0 else 0.0
                    except Exception:
                        return float(x)
                def _dms_to_deg(dms):
                    d = _to_deg(dms[0]) if len(dms) > 0 else 0.0
                    m = _to_deg(dms[1]) if len(dms) > 1 else 0.0
                    s = _to_deg(dms[2]) if len(dms) > 2 else 0.0
                    return d + (m / 60.0) + (s / 3600.0)
                if gps_map:
                    lat = lon = None
                    if 'GPSLatitude' in gps_map and 'GPSLatitudeRef' in gps_map:
                        lat = _dms_to_deg(gps_map['GPSLatitude'])
                        if str(gps_map['GPSLatitudeRef']).upper().startswith('S'):
                            lat = -lat
                    if 'GPSLongitude' in gps_map and 'GPSLongitudeRef' in gps_map:
                        lon = _dms_to_deg(gps_map['GPSLongitude'])
                        if str(gps_map['GPSLongitudeRef']).upper().startswith('W'):
                            lon = -lon
                    out["gps"] = {"lat": lat, "lon": lon}
            except Exception:
                pass
            return out
    except Exception:
        return {}


def _preprocess_image_for_model(image_path: str, max_side: int = 1024, jpeg_quality: int = 80) -> bytes | None:
    """이미지를 1024px 장변, sRGB, JPEG Q≈80으로 인코딩하여 바이트로 반환."""
    if Image is None or not os.path.exists(image_path):
        return None
    try:
        with Image.open(image_path) as im:
            im = im.convert("RGB")
            # sRGB 변환(ICC 있으면 변환 시도)
            try:
                prof = im.info.get("icc_profile")
                if ImageCms is not None and prof:
                    src = ImageCms.ImageCmsProfile(io.BytesIO(prof))
                    dst = ImageCms.createProfile("sRGB")
                    im = ImageCms.profileToProfile(im, src, dst, outputMode="RGB")
            except Exception:
                pass
            w, h = im.size
            scale = 1.0
            if max(w, h) > max_side:
                scale = max_side / float(max(w, h))
                im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=int(jpeg_quality), optimize=True, subsampling=0)
            return buf.getvalue()
    except Exception as e:
        try:
            _log.error("preprocess_fail | file=%s | err=%s", os.path.basename(image_path), str(e))
        except Exception:
            pass
        return None


def _build_prompt(context: AnalysisContext, exif_summary: Dict[str, Any]) -> str:
    """시스템/지시 메시지는 서버측에서 구성된다고 가정하고, 여기서는 사용자 입력 블록만 작성."""
    lines = []
    lines.append("[컨텍스트]")
    lines.append(f"- purpose: {context.purpose}")
    lines.append(f"- tone: {context.tone}")
    lines.append(f"- language: {context.language}")
    if context.user_keywords:
        lines.append(f"- user_keywords: {context.user_keywords}")
    lines.append("")
    if exif_summary:
        lines.append("[EXIF 요약]")
        for k in [
            "make","model","lens","aperture","shutter","iso",
            "focal_length_mm","focal_length_35mm_eq_mm","datetime_original",
        ]:
            v = exif_summary.get(k)
            if v is not None:
                lines.append(f"{k}: {v}")
        gps = exif_summary.get("gps") or {}
        lat = gps.get("lat")
        lon = gps.get("lon")
        if lat is not None and lon is not None:
            lines.append(f"gps: {{lat: {lat}, lon: {lon}}}")
    return "\n".join(lines)


class AIAnalysisService:
    """멀티모달 모델 호출 래퍼. 환경에 따라 폴백을 제공."""

    def __init__(self):
        self._provider = os.getenv("AI_PROVIDER", "openai")
        # 안전한 기본값과 허용 목록 적용
        env_model = (os.getenv("AI_MODEL", "gpt-5") or "").strip()
        allowed_models = {"gpt-5"}
        self._model = env_model if env_model in allowed_models else "gpt-5"
        self._api_key = os.getenv("OPENAI_API_KEY")

    def analyze(self, image_path: str, context: Optional[AnalysisContext] = None) -> Dict[str, Any]:
        ctx = context or AnalysisContext()
        exif_summary = _extract_exif_summary(image_path)
        user_prompt = _build_prompt(ctx, exif_summary)
        img_bytes = _preprocess_image_for_model(image_path)
        if img_bytes is None:
            return self._fallback_result(exif_summary, note="이미지 전처리에 실패하여 텍스트 전용으로 폴백")

        try:
            result = self._call_openai(image_bytes=img_bytes, prompt=user_prompt, context=ctx)
            return self._validate_and_normalize(result, exif_summary)
        except Exception as e:
            try:
                _log.warning("ai_call_fallback | err=%s", str(e))
            except Exception:
                pass
            return self._fallback_result(exif_summary, note=f"폴백: {type(e).__name__}")

    def _call_openai(self, image_bytes: bytes, prompt: str, context: AnalysisContext) -> Dict[str, Any]:
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY 없음")
        # 이미지 base64 인라인 전송
        b64 = base64.b64encode(image_bytes).decode("ascii")
        system_msg = (
            "당신은 사진 편집 어시스턴트다. 사용자는 사진 캡션/설명/태그/촬영 의도 추정을 원한다.\n"
            f"- 항상 지정된 언어({context.language})로 출력한다. 이모지·이모티콘·해시태그 금지.\n"
            "- 반드시 JSON 스키마에 맞게만 출력한다. 여분 텍스트 금지.\n"
            "- 사실성 우선, EXIF는 보조 근거. 불확실 요소는 null 또는 notes에 '추정' 기록.\n"
        )
        instruction = (
            "- short_caption: 12~18단어\n"
            "- long_caption: 1~2문단(80~160자)\n"
            "- tags: 6~10개, 소문자/한글 원형화\n"
            "- subjects: [사람, 풍경, 도시, 야생동물, 제품] 중에서 선택\n"
            "- camera_settings: EXIF 없으면 null\n"
            "- gps.place_guess: 좌표 없으면 null\n"
            "- safety/sensitive: 민감 요소 표시\n"
            "- confidence: 0.0~1.0\n"
            "- 금지: 인종/성별 단정, 상표 추측, 광고 문구\n"
        )
        # Responses API (OpenAI 1.x 권장 경로만 사용)
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:
            raise RuntimeError(f"openai SDK 로드 실패: {e}")

        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=self._api_key)

        # 1) Chat Completions 멀티모달 경로(권장)
        try:
            messages = [
                {"role": "system", "content": system_msg},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction + "\n\n" + prompt},
                        # 일부 모델에서 detail 필드가 400을 유발하므로 제외
                        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
                    ],
                },
            ]
            comp = client.chat.completions.create(
                model=self._model,
                messages=messages
            )
            text = comp.choices[0].message.content or "{}"
            return json.loads(text)
        except Exception as e:
            # 400 등 오류 내용 로깅 시도
            try:
                body = getattr(getattr(e, "response", None), "json", lambda: {})()
                _log.warning("openai_chat_fail | model=%s | body=%s", self._model, body)
            except Exception:
                try:
                    _log.warning("openai_chat_fail | model=%s | err=%s", self._model, str(e))
                except Exception:
                    pass
            pass

        # Responses API는 사용하지 않음

    def _validate_and_normalize(self, data: Dict[str, Any], exif_summary: Dict[str, Any]) -> Dict[str, Any]:
        # 기본 스키마 채우기
        result = json.loads(json.dumps(SCHEMA_DEFAULT))
        try:
            for k, v in data.items():
                result[k] = v
        except Exception:
            pass
        # camera_settings, gps 보정
        cam = result.get("camera_settings") or {}
        if exif_summary:
            # EXIF 기반 보정(충돌 시 notes에 추정으로 남김)
            if cam.get("aperture") is None and exif_summary.get("aperture"):
                cam["aperture"] = exif_summary.get("aperture")
            if cam.get("shutter") is None and exif_summary.get("shutter"):
                cam["shutter"] = exif_summary.get("shutter")
            if cam.get("iso") is None and exif_summary.get("iso") is not None:
                cam["iso"] = exif_summary.get("iso")
            if cam.get("focal_length_mm") is None and exif_summary.get("focal_length_mm") is not None:
                cam["focal_length_mm"] = exif_summary.get("focal_length_mm")
            if cam.get("focal_length_35mm_eq_mm") is None and exif_summary.get("focal_length_35mm_eq_mm") is not None:
                cam["focal_length_35mm_eq_mm"] = exif_summary.get("focal_length_35mm_eq_mm")
        result["camera_settings"] = cam

        gps = result.get("gps") or {"lat": None, "lon": None, "place_guess": None}
        exif_gps = (exif_summary or {}).get("gps") or {}
        if gps.get("lat") is None and exif_gps.get("lat") is not None:
            gps["lat"] = exif_gps.get("lat")
        if gps.get("lon") is None and exif_gps.get("lon") is not None:
            gps["lon"] = exif_gps.get("lon")
        result["gps"] = gps

        # 최소 검증
        if not isinstance(result.get("tags"), list):
            result["tags"] = []
        if not isinstance(result.get("subjects"), list):
            result["subjects"] = []
        if not isinstance(result.get("safety"), dict):
            result["safety"] = {"nsfw": False, "sensitive": []}
        if not isinstance(result.get("confidence"), (int, float)):
            result["confidence"] = 0.0
        if not isinstance(result.get("notes"), str):
            result["notes"] = ""
        return result

    def _fallback_result(self, exif_summary: Dict[str, Any], note: str = "") -> Dict[str, Any]:
        result = json.loads(json.dumps(SCHEMA_DEFAULT))
        # EXIF는 보조로 채움
        cam = result["camera_settings"]
        for k in ["aperture", "shutter", "iso", "focal_length_mm", "focal_length_35mm_eq_mm"]:
            if exif_summary.get(k) is not None:
                cam[k] = exif_summary.get(k)
        gps = result["gps"]
        exif_gps = (exif_summary or {}).get("gps") or {}
        gps["lat"] = exif_gps.get("lat")
        gps["lon"] = exif_gps.get("lon")
        # 폴백 노트 및 보수적 신뢰도
        result["notes"] = (note or "") + " | 모델 호출 실패로 텍스트 전용/기본값을 반환합니다."
        result["confidence"] = 0.3
        return result


