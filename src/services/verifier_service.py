from __future__ import annotations

import os
import json
import hashlib
from typing import Dict, Any, List, Tuple

from ..utils.logging_setup import get_logger

_log = get_logger("svc.Verifier")


def _sha1(b: bytes) -> str:
    try:
        return hashlib.sha1(b).hexdigest()
    except Exception:
        return ""


class VerifierService:
    """GPT 비전을 활용해 후보 이미지가 질의 장면과 일치하는지 재검증.

    결과 스키마(JSON): { match: bool, confidence: float, reasons: string }
    캐시 키: sha1(image_bytes_1024_jpeg) + '|' + sha1(prompt)
    """

    def __init__(self):
        self._api_key = os.getenv("OPENAI_API_KEY")
        # 기본 모델은 gpt-4o 계열 권장
        m = os.getenv("AI_VERIFY_MODEL", "gpt-5-nano").strip()
        self._model = m if m else "gpt-5-nano"
        base_dir = os.path.join(os.path.expanduser("~"), ".jusawi")
        try:
            os.makedirs(base_dir, exist_ok=True)
        except Exception:
            pass
        self._cache_path = os.path.join(base_dir, "verify_cache.jsonl")
        self._cache = {}
        try:
            if os.path.exists(self._cache_path):
                with open(self._cache_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            obj = json.loads(line)
                            self._cache[obj.get("key","?")] = obj.get("value")
                        except Exception:
                            pass
        except Exception:
            pass

    def _save_cache(self, key: str, value: Dict[str, Any]) -> None:
        self._cache[key] = value
        try:
            with open(self._cache_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _preprocess(self, image_path: str) -> bytes | None:
        try:
            from PIL import Image  # type: ignore
        except Exception:
            return None
        try:
            from .ai_analysis_service import _preprocess_image_for_model  # reuse
        except Exception:
            return None
        try:
            max_side = int(os.getenv("AI_VERIFY_MAX_SIDE", "768") or 768)
        except Exception:
            max_side = 768
        try:
            jpeg_quality = int(os.getenv("AI_VERIFY_JPEG_QUALITY", "70") or 70)
        except Exception:
            jpeg_quality = 70
        try:
            target_bytes = int(os.getenv("AI_VERIFY_TARGET_BYTES", "300000") or 300000)
        except Exception:
            target_bytes = 300000
        try:
            min_side = int(os.getenv("AI_VERIFY_MIN_SIDE", "320") or 320)
        except Exception:
            min_side = 320
        return _preprocess_image_for_model(
            image_path,
            max_side=max_side,
            jpeg_quality=jpeg_quality,
            target_bytes=target_bytes,
            min_side=min_side,
        )

    def verify(self, image_path: str, query_text: str) -> Dict[str, Any]:
        if not self._api_key:
            return {"match": False, "confidence": 0.0, "reasons": "API 키 없음"}
        import time
        t0 = time.monotonic()
        img = self._preprocess(image_path)
        if not img:
            return {"match": False, "confidence": 0.0, "reasons": "이미지 전처리 실패"}
        t1 = time.monotonic()
        key = _sha1(img) + "|" + _sha1(query_text.encode("utf-8"))
        if key in self._cache:
            out = dict(self._cache[key])
            if os.getenv("AI_VERIFY_LOG", "0") == "1":
                try:
                    _log.info("verify_cache_hit | file=%s | conf=%.3f | dt_pre=%.3fs", os.path.basename(image_path), float(out.get("confidence",0.0)), (t1-t0))
                except Exception:
                    pass
            return out

        # 프롬프트 강화: 색상/객관 요소 중시, 허위 추론 금지, JSON 강제
        system_msg = (
            "당신은 사진 검증 어시스턴트다. 사용자 질의와 이미지의 일치 여부를 판단한다.\n"
            "- 반드시 JSON으로만 답한다(여분 텍스트 금지).\n"
            "- 보이는 정보에만 근거한다. 추측/환각 금지.\n"
            "- 질의에 특정 색상/수량/객체가 명시되면 해당 요소 부재 시 match=false로 판정한다.\n"
        )
        instruction = (
            "스키마:\n"
            '{"match": true|false, "confidence": 0.0~1.0, "reasons": "간단 근거"}\n'
            "판정 기준:\n"
            "- 장면/주요 객체/행동/관계/색상을 종합 판단.\n"
            "- 색상 언급이 있는 경우, 해당 색이 핵심 대상에 실제로 보이는지 확인.\n"
            "- 불명확하면 match=false에 가깝게 낮은 confidence로.\n"
        )

        import base64
        from openai import OpenAI  # type: ignore
        try:
            timeout_s = float(os.getenv("AI_VERIFY_TIMEOUT", "10") or 10)
        except Exception:
            timeout_s = 10.0
        try:
            top_p = float(os.getenv("AI_VERIFY_TOP_P", "1") or 1)
        except Exception:
            top_p = 1.0
        try:
            n = int(os.getenv("AI_VERIFY_N", "1") or 1)
        except Exception:
            n = 1
        n = max(1, min(8, n))
        client = OpenAI(api_key=self._api_key, timeout=timeout_s)
        b64 = base64.b64encode(img).decode("ascii")
        messages = [
            {"role": "system", "content": system_msg},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction + "\n장면 설명:" + query_text},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
                ],
            },
        ]
        try:
            t2 = time.monotonic()
            resp = client.chat.completions.create(
                model=self._model,
                messages=messages,
                top_p=top_p,
                n=n,
            )
            t3 = time.monotonic()
            best_conf = 0.0
            best = {"match": False, "confidence": 0.0, "reasons": ""}
            # 집계 방식: max(기본). mean을 원하면 AI_VERIFY_AGG=mean
            agg = (os.getenv("AI_VERIFY_AGG", "max") or "max").lower()
            confs: List[float] = []
            outs: List[Dict[str, Any]] = []
            for ch in resp.choices:
                txt = (getattr(getattr(ch, "message", None), "content", None) or "{}")
                try:
                    data = json.loads(txt)
                    out = {
                        "match": bool(data.get("match", False)),
                        "confidence": float(data.get("confidence", 0.0)),
                        "reasons": str(data.get("reasons", "")),
                    }
                except Exception:
                    out = {"match": False, "confidence": 0.0, "reasons": "parse_fail"}
                outs.append(out)
                confs.append(float(out.get("confidence", 0.0)))
                if float(out.get("confidence", 0.0)) > best_conf:
                    best_conf = float(out.get("confidence", 0.0))
                    best = out
            if agg == "mean" and confs:
                mean_conf = sum(confs) / float(len(confs))
                # mean에서는 match를 best 기준으로 유지, confidence만 평균
                best = dict(best)
                best["confidence"] = float(mean_conf)
            self._save_cache(key, best)
            if os.getenv("AI_VERIFY_LOG", "0") == "1":
                try:
                    _log.info("verify_ok | file=%s | conf=%.3f | n=%d | dt_pre=%.3fs | dt_api=%.3fs", os.path.basename(image_path), float(best.get("confidence",0.0)), int(n), (t1-t0), (t3-t2))
                except Exception:
                    pass
            return best
        except Exception as e:
            try:
                _log.warning("verify_fail | err=%s", str(e))
            except Exception:
                pass
            return {"match": False, "confidence": 0.0, "reasons": "검증 실패"}

    @staticmethod
    def pass_threshold(conf: float, mode: str) -> bool:
        # mode: loose/normal/strict (정확도 우선으로 상향)
        if mode == "strict":
            t = 0.75
        elif mode == "loose":
            t = 0.50
        else:
            t = 0.65
        try:
            return float(conf) >= float(t)
        except Exception:
            return False


