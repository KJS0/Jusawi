from __future__ import annotations

import os
import json
import sqlite3
import math
from typing import List, Tuple, Optional, Dict, Any
try:
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover
    _np = None  # type: ignore

try:
    from PIL import Image, ExifTags  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ExifTags = None  # type: ignore

from ..utils.logging_setup import get_logger

_log = get_logger("svc.Embeddings")


class EmbeddingsService:
    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY")
        self._model = os.getenv("AI_EMBED_MODEL", "text-embedding-3-small")
        base_dir = os.path.join(os.path.expanduser("~"), ".jusawi")
        try:
            os.makedirs(base_dir, exist_ok=True)
        except Exception:
            pass
        self._db_path = os.path.join(base_dir, "embeddings.sqlite3")
        self._ensure_db()
        # 간단한 쿼리 캐시(메모리)
        self._query_cache: Dict[str, List[Tuple[str, float]]] = {}

    def _ensure_db(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY,
                    path TEXT UNIQUE,
                    mtime INTEGER,
                    text TEXT,
                    dim INTEGER,
                    model TEXT,
                    vec BLOB
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_images_path ON images(path)")
            con.commit()
        finally:
            con.close()

    def _load_analysis_json(self, image_path: str) -> Optional[Dict[str, Any]]:
        base, _ = os.path.splitext(image_path)
        json_path = base + "_analysis.json"
        if not os.path.exists(json_path):
            return None
        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    def _build_exif_snippet(self, image_path: str) -> str:
        if Image is None or not os.path.exists(image_path):
            return ""
        try:
            with Image.open(image_path) as im:
                exif_map = {}
                try:
                    exif = im.getexif()
                    if exif:
                        for tag_id, value in exif.items():
                            name = getattr(ExifTags, 'TAGS', {}).get(tag_id, str(tag_id)) if ExifTags else str(tag_id)
                            exif_map[name] = value
                except Exception:
                    pass
                keys = [
                    "DateTimeOriginal", "Make", "Model", "LensModel", "FNumber",
                    "ExposureTime", "ISOSpeedRatings", "FocalLength", "FocalLengthIn35mmFilm"
                ]
                parts = []
                for k in keys:
                    v = exif_map.get(k)
                    if v:
                        parts.append(f"{k}:{v}")
                # GPS 좌표만 단순 문자열로
                gps = exif_map.get("GPSInfo")
                if isinstance(gps, dict) and gps:
                    parts.append("GPS:present")
                return " | ".join(parts)
        except Exception:
            return ""

    def build_text_blob(self, image_path: str) -> str:
        data = self._load_analysis_json(image_path) or {}
        parts: List[str] = []
        for k in ["short_caption", "long_caption", "shooting_intent"]:
            v = str(data.get(k) or "").strip()
            if v:
                parts.append(v)
        # tags/subjects
        for k in ["tags", "subjects"]:
            arr = data.get(k) or []
            if isinstance(arr, list) and arr:
                parts.append(", ".join([str(x) for x in arr]))
        # EXIF 스니펫 추가
        exif_snip = self._build_exif_snippet(image_path)
        if exif_snip:
            parts.append(exif_snip)
        return " | ".join(parts)

    def embed_text(self, text: str) -> List[float]:
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY 없음")
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=self._api_key)
        resp = client.embeddings.create(model=self._model, input=[text or " "])
        return list(resp.data[0].embedding)

    def _get_mtime(self, path: str) -> int:
        try:
            return int(os.path.getmtime(path))
        except Exception:
            return 0

    def upsert_image(self, image_path: str) -> bool:
        if not image_path or not os.path.exists(image_path):
            return False
        mtime = self._get_mtime(image_path)
        con = sqlite3.connect(self._db_path)
        try:
            cur = con.cursor()
            cur.execute("SELECT mtime FROM images WHERE path=?", (image_path,))
            row = cur.fetchone()
            if row and int(row[0]) == mtime:
                return True
            text = self.build_text_blob(image_path)
            vec = self.embed_text(text)
            dim = len(vec)
            vec_bytes = (",".join(f"{x:.7f}" for x in vec)).encode("utf-8")
            cur.execute(
                "INSERT INTO images(path, mtime, text, dim, model, vec) VALUES(?,?,?,?,?,?)"
                " ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, text=excluded.text, dim=excluded.dim, model=excluded.model, vec=excluded.vec",
                (image_path, mtime, text, dim, self._model, vec_bytes),
            )
            con.commit()
            return True
        except Exception as e:
            try:
                _log.warning("embed_upsert_fail | file=%s | err=%s", os.path.basename(image_path), str(e))
            except Exception:
                pass
            return False
        finally:
            con.close()

    def _parse_vec(self, b: bytes) -> List[float]:
        try:
            s = b.decode("utf-8")
            return [float(x) for x in s.split(",") if x]
        except Exception:
            return []

    def _cosine(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = 0.0
        na = 0.0
        nb = 0.0
        for i in range(len(a)):
            va = a[i]
            vb = b[i]
            dot += va * vb
            na += va * va
            nb += vb * vb
        if na <= 0.0 or nb <= 0.0:
            return 0.0
        return dot / (math.sqrt(na) * math.sqrt(nb))

    def query(self, text: str, top_k: int = 50) -> List[Tuple[str, float]]:
        # 간단 캐시 키: 쿼리 문자열
        key = (text or " ")
        cached = self._query_cache.get(key)
        if cached is not None:
            return cached[: max(1, int(top_k))]
        qvec = self.embed_text(text or " ")
        con = sqlite3.connect(self._db_path)
        try:
            cur = con.cursor()
            cur.execute("SELECT path, vec FROM images")
            rows = cur.fetchall()
            # NumPy 가속: 벡터화 코사인
            paths: List[str] = []
            mat = []
            for path, vec_b in rows:
                vec = self._parse_vec(vec_b)
                if not vec:
                    continue
                paths.append(path)
                mat.append(vec)
            if not paths:
                return []
            if _np is not None:
                try:
                    a = _np.asarray(qvec, dtype=_np.float32)
                    B = _np.asarray(mat, dtype=_np.float32)
                    num = B @ a
                    a_norm = _np.linalg.norm(a) + 1e-8
                    b_norm = _np.linalg.norm(B, axis=1) + 1e-8
                    scores = (num / (a_norm * b_norm)).tolist()
                except Exception:
                    scores = [self._cosine(qvec, v) for v in mat]
            else:
                scores = [self._cosine(qvec, v) for v in mat]
            scored = sorted(zip(paths, scores), key=lambda x: x[1], reverse=True)
            top = scored[: max(1, int(top_k))]
            self._query_cache[key] = top
            return top
        finally:
            con.close()


