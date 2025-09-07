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
        m = os.getenv("AI_VERIFY_MODEL", "gpt-4o").strip()
        self._model = m if m else "gpt-4o"
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
        return _preprocess_image_for_model(image_path)

    def verify(self, image_path: str, query_text: str) -> Dict[str, Any]:
        if not self._api_key:
            return {"match": False, "confidence": 0.0, "reasons": "API 키 없음"}
        img = self._preprocess(image_path)
        if not img:
            return {"match": False, "confidence": 0.0, "reasons": "이미지 전처리 실패"}
        key = _sha1(img) + "|" + _sha1(query_text.encode("utf-8"))
        if key in self._cache:
            return dict(self._cache[key])

        # 프롬프트: 간결/정확/JSON 강제
        system_msg = (
            "당신은 사진 검증 어시스턴트다. 사용자가 제시한 장면 설명과 이미지가 일치하는지 평가한다.\n"
            "- 반드시 JSON으로만 답하라. 여분 텍스트 금지.\n"
        )
        instruction = (
            "다음 스키마로만 출력:\n"
            '{"match": true|false, "confidence": 0.0~1.0, "reasons": "간단 근거"}\n'
        )

        import base64
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=self._api_key)
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
            resp = client.chat.completions.create(model=self._model, messages=messages, temperature=0.0)
            txt = resp.choices[0].message.content or "{}"
            data = json.loads(txt)
            # 최소 필드 보정
            out = {
                "match": bool(data.get("match", False)),
                "confidence": float(data.get("confidence", 0.0)),
                "reasons": str(data.get("reasons", "")),
            }
            self._save_cache(key, out)
            return out
        except Exception as e:
            try:
                _log.warning("verify_fail | err=%s", str(e))
            except Exception:
                pass
            return {"match": False, "confidence": 0.0, "reasons": "검증 실패"}

    @staticmethod
    def pass_threshold(conf: float, mode: str) -> bool:
        # mode: loose/normal/strict
        t = 0.5 if mode == "loose" else (0.75 if mode == "strict" else 0.6)
        try:
            return float(conf) >= float(t)
        except Exception:
            return False


