from __future__ import annotations

import os
import io
import sqlite3
import json
from typing import List, Tuple, Optional
import inspect
import importlib

try:  # optional dependency
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore

SentenceTransformer = None  # lazy import
open_clip = None  # lazy import
torch = None  # lazy import

from ..utils.logging_setup import get_logger

_log = get_logger("svc.OfflineVerifier")


class OfflineVerifierService:
    """
    오프라인 CLIP 임베딩으로 텍스트-이미지 유사도 기반 재검증/재정렬.
    - 의존성: sentence_transformers (선택). 없으면 available=False.
    - 이미지 벡터는 ~/.jusawi/offline_clip.sqlite3 에 캐시.
    """

    def __init__(self):
        # 다국어 질의를 고려해 기본값을 멀티링구얼 모델로 설정 (HuggingFace 경로 포함)
        self._model_name = os.getenv(
            "OFFLINE_CLIP_MODEL",
            "sentence-transformers/clip-ViT-B-32-multilingual-v1",
        ).strip()
        self._st_available = True  # determined on demand
        self._st_supports_images = False
        self._model: Optional[SentenceTransformer] = None
        # open_clip fallback
        self._oc_available = True  # determined on demand
        self._oc_model = None
        self._oc_preprocess = None
        self._oc_tokenizer = None
        self._device = "cpu"
        self.engine = ""  # 'st' | 'open_clip' | ''
        self._force = ""
        base_dir = os.path.join(os.path.expanduser("~"), ".jusawi")
        try:
            os.makedirs(base_dir, exist_ok=True)
        except Exception:
            pass
        self._db_path = os.path.join(base_dir, "offline_clip.sqlite3")
        self._ensure_db()
        if self._available:
            try:
                # lazy load on first use to avoid blocking init
                pass
            except Exception:
                self._available = False

    @property
    def available(self) -> bool:
        return bool(self._st_available or self._oc_available)

    def is_ready(self) -> bool:
        """엔진이 실제로 임베딩을 계산할 준비가 되었는지 확인."""
        # SentenceTransformers 경로
        if self._st_available:
            if self._model is None:
                self._ensure_model()
            if self._model is not None and self._st_supports_images:
                self.engine = "st"
                return True
        # OpenCLIP 경로
        if self._oc_available:
            if self._oc_model is None:
                self._ensure_open_clip()
            if self._oc_model is not None and self._oc_preprocess is not None:
                self.engine = "open_clip"
                return True
        return False

    def prepare(self) -> tuple[bool, str]:
        """엔진을 로드해 사용할 준비를 한다. (ready, engine|error)"""
        # Auto: Try ST, then OpenCLIP
        if self._ensure_model():
            try:
                from PIL import Image as _PIL  # type: ignore
                test = _PIL.new("RGB", (1, 1), (255, 0, 0))
                vec = self._model.encode(images=[test], batch_size=1, convert_to_numpy=True, normalize_embeddings=True)
                if vec is not None:
                    self._st_supports_images = True
                    self.engine = "st"
                    try:
                        _log.info("offline_ready | engine=st | model=%s", self._model_name)
                    except Exception:
                        pass
                    return True, self.engine
            except Exception as te:
                try:
                    _log.warning("offline_st_test_fail | err=%s", str(te))
                except Exception:
                    pass
        if self._ensure_open_clip():
            self.engine = "open_clip"
            try:
                _log.info("offline_ready | engine=open_clip")
            except Exception:
                pass
            return True, self.engine
        return False, "no_engine"

    def _ensure_model(self) -> bool:
        if not self._st_available:
            return False
        if self._model is not None:
            return True
        try:
            # Lazy import here
            global SentenceTransformer
            if SentenceTransformer is None:
                try:
                    from sentence_transformers import SentenceTransformer as _ST  # type: ignore
                    SentenceTransformer = _ST
                except Exception as ie:
                    try:
                        _log.warning("st_import_fail | err=%s", str(ie))
                    except Exception:
                        pass
                    self._st_available = False
                    return False
            candidates = [self._model_name]
            # 레포 접두어 누락 시 보정 후보 추가
            if "/" not in self._model_name:
                candidates.append("sentence-transformers/" + self._model_name)
            # 일반 단일언어 폴백
            candidates.append("sentence-transformers/clip-ViT-B-32")
            last_err = None
            for name in candidates:
                try:
                    self._model = SentenceTransformer(name)
                    # 이미지 인코딩 지원 여부 확인
                    try:
                        sig = inspect.signature(self._model.encode)
                        self._st_supports_images = any(
                            p.kind in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                            and p.name == "images" for p in sig.parameters.values()
                        )
                    except Exception:
                        self._st_supports_images = False
                    return True
                except Exception as e:
                    last_err = e
                    continue
            raise last_err or RuntimeError("model_load_failed")
        except Exception as e:
            try:
                _log.warning("offline_model_load_fail | model=%s | err=%s", self._model_name, str(e))
            except Exception:
                pass
            self._st_available = False
            return False

    def _ensure_open_clip(self) -> bool:
        if not self._oc_available:
            return False
        if self._oc_model is not None and self._oc_preprocess is not None and self._oc_tokenizer is not None:
            return True
        try:
            # Lazy import here
            global open_clip, torch
            if open_clip is None or torch is None:
                try:
                    import open_clip as _OC  # type: ignore
                    import torch as _TH  # type: ignore
                    open_clip = _OC
                    torch = _TH
                except Exception as ie:
                    try:
                        _log.warning("open_clip_import_fail | err=%s", str(ie))
                    except Exception:
                        pass
                    self._oc_available = False
                    return False
            oc_model_name = os.getenv("OPENCLIP_MODEL", "ViT-B-32").strip() or "ViT-B-32"
            oc_pretrained = os.getenv("OPENCLIP_PRETRAINED", "laion2b_s34b_b79k").strip() or "laion2b_s34b_b79k"
            m, preprocess, tokenizer = open_clip.create_model_and_transforms(oc_model_name, pretrained=oc_pretrained, device=self._device)
            m.eval()
            self._oc_model = m
            self._oc_preprocess = preprocess
            self._oc_tokenizer = tokenizer
            return True
        except Exception as e:
            try:
                _log.warning("open_clip_load_fail | err=%s", str(e))
            except Exception:
                pass
            self._oc_available = False
            return False

    def _ensure_db(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                    path TEXT PRIMARY KEY,
                    mtime INTEGER,
                    model TEXT,
                    dim INTEGER,
                    vec BLOB
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_vectors_path ON vectors(path)")
            con.commit()
        finally:
            con.close()

    def _get_mtime(self, path: str) -> int:
        try:
            return int(os.path.getmtime(path))
        except Exception:
            return 0

    def _read_vec(self, b: bytes) -> List[float]:
        try:
            s = b.decode("utf-8")
            return [float(x) for x in s.split(",") if x]
        except Exception:
            return []

    def _write_vec(self, vec: List[float]) -> bytes:
        return (",".join(f"{x:.7f}" for x in vec)).encode("utf-8")

    def _embed_image(self, path: str) -> Optional[List[float]]:
        # Prefer SentenceTransformers if it supports image encoding
        if self._ensure_model() and self._st_supports_images and Image is not None:
            try:
                with Image.open(path) as im:
                    im = im.convert("RGB")
                    vec = self._model.encode(
                        images=[im],
                        batch_size=1,
                        convert_to_numpy=True,
                        normalize_embeddings=True,
                    )
                    return list(vec[0].tolist())
            except Exception as e:
                try:
                    _log.warning("offline_img_embed_fail | file=%s | err=%s", os.path.basename(path), str(e))
                except Exception:
                    pass
        # Fallback to open_clip
        if self._ensure_open_clip() and Image is not None:
            return None
        try:
            with Image.open(path) as im:
                im = im.convert("RGB")
                img = self._oc_preprocess(im).unsqueeze(0)
                with torch.no_grad():
                    feat = self._oc_model.encode_image(img)
                    feat = feat / feat.norm(dim=-1, keepdim=True)
                return list(feat[0].cpu().tolist())
        except Exception as e:
            try:
                _log.warning("offline_img_embed_fail | file=%s | err=%s", os.path.basename(path), str(e))
            except Exception:
                pass
            return None

    def _embed_text(self, text: str) -> Optional[List[float]]:
        if self._ensure_model():
            try:
                vec = self._model.encode(
                    sentences=[text or " "],
                    batch_size=1,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )
                return list(vec[0].tolist())
            except Exception as e:
                try:
                    _log.warning("offline_txt_embed_fail | err=%s", str(e))
                except Exception:
                    pass
        # Fallback to open_clip
        if self._ensure_open_clip():
            try:
                tok = self._oc_tokenizer([text or " "])
                with torch.no_grad():
                    feat = self._oc_model.encode_text(tok)
                    feat = feat / feat.norm(dim=-1, keepdim=True)
                return list(feat[0].cpu().tolist())
            except Exception as e:
                try:
                    _log.warning("offline_txt_embed_fail | oc | err=%s", str(e))
                except Exception:
                    pass
            return None

    def _get_or_compute_image_vec(self, path: str) -> Optional[List[float]]:
        mtime = self._get_mtime(path)
        con = sqlite3.connect(self._db_path)
        try:
            cur = con.cursor()
            cur.execute("SELECT mtime, dim, vec FROM vectors WHERE path=? AND model=?", (path, self._model_name))
            row = cur.fetchone()
            if row and int(row[0]) == mtime:
                return self._read_vec(row[2])
        except Exception:
            pass
        finally:
            con.close()
        vec = self._embed_image(path)
        if not vec:
            return None
        con = sqlite3.connect(self._db_path)
        try:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO vectors(path, mtime, model, dim, vec) VALUES(?,?,?,?,?)"
                " ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, model=excluded.model, dim=excluded.dim, vec=excluded.vec",
                (path, mtime, self._model_name, len(vec), self._write_vec(vec)),
            )
            con.commit()
        except Exception:
            pass
        finally:
            con.close()
        return vec

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
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
        import math
        return dot / (math.sqrt(na) * math.sqrt(nb))

    @staticmethod
    def threshold_for(mode: str) -> float:
        # 경험적 초기값. 데이터에 맞게 조정 가능
        if mode == "loose":
            return 0.24
        if mode == "strict":
            return 0.30
        return 0.27

    def rerank_offline(self, results: List[Tuple[str, float]], query_text: str, mode: str = "normal") -> List[Tuple[str, float]]:
        if not self.available:
            return results
        qvec = self._embed_text(query_text)
        if not qvec:
            return results
        th = self.threshold_for(mode)
        kept: List[Tuple[str, float]] = []
        for path, sim in results:
            ivec = self._get_or_compute_image_vec(path)
            if not ivec:
                continue
            c = self._cosine(qvec, ivec)
            if c >= th:
                score = c  # CLIP 점수 우선
                kept.append((path, float(score)))
        kept.sort(key=lambda x: x[1], reverse=True)
        return kept

    def search_offline(self, image_paths: List[str], query_text: str, top_k: int = 50) -> List[Tuple[str, float]]:
        """완전 오프라인 검색: 모든 후보의 이미지 임베딩과 쿼리 임베딩(CLIP)으로 유사도를 계산해 상위 반환."""
        if not self.available:
            return []
        qvec = self._embed_text(query_text)
        if not qvec:
            return []
        scored: List[Tuple[str, float]] = []
        for p in image_paths:
            ivec = self._get_or_compute_image_vec(p)
            if not ivec:
                continue
            c = self._cosine(qvec, ivec)
            scored.append((p, float(c)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[: max(1, int(top_k))]


