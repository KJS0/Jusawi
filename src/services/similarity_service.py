from __future__ import annotations

import os, json
from typing import Dict, List, Tuple, Optional
import numpy as np

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    _HAS_CLIP = True
except Exception:
    _HAS_CLIP = False

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore

try:
    import imagehash  # type: ignore
    _HAS_PHASH = True
except Exception:
    _HAS_PHASH = False

try:  # optional ANN
    import hnswlib  # type: ignore
    _HAS_HNSW = True
except Exception:
    _HAS_HNSW = False

_SUPPORTED = {'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff','.gif'}

def _cos(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a) + 1e-9
    nb = np.linalg.norm(b) + 1e-9
    return float(np.dot(a, b) / (na * nb))


class SimilarityIndex:
    def __init__(self):
        self._model = None
        self._cache_dir = os.path.join(os.path.expanduser("~"), ".jusawi_sim_cache")
        try:
            os.makedirs(self._cache_dir, exist_ok=True)
        except Exception:
            pass
        self._index: Dict[str, Dict] = {}

    def _ensure_model(self):
        if self._model is None and _HAS_CLIP:
            # CLIP ViT-B/32
            self._model = SentenceTransformer("clip-ViT-B-32")

    def _is_image(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in _SUPPORTED

    def _vec_image(self, path: str) -> Optional[np.ndarray]:
        if Image is None:
            return None
        try:
            if _HAS_CLIP:
                self._ensure_model()
                with Image.open(path) as im:
                    im = im.convert("RGB")
                    v = self._model.encode(im, convert_to_numpy=True, normalize_embeddings=True)  # type: ignore
                return np.asarray(v, dtype=np.float32)
            elif _HAS_PHASH:
                with Image.open(path) as im:
                    ph = imagehash.phash(im)
                bits = np.unpackbits(np.array([int(str(ph),16)], dtype='>u8').view('>u1'))
                vec = (bits.astype(np.float32) * 2.0 - 1.0)
                return vec
        except Exception:
            return None
        return None

    def _vec_text(self, text: str) -> Optional[np.ndarray]:
        if not text.strip() or not _HAS_CLIP:
            return None
        try:
            self._ensure_model()
            v = self._model.encode([text], convert_to_numpy=True, normalize_embeddings=True)  # type: ignore
            return np.asarray(v[0], dtype=np.float32)
        except Exception:
            return None

    def _phash64(self, path: str) -> Optional[int]:
        if not _HAS_PHASH or Image is None:
            return None
        try:
            with Image.open(path) as im:
                h = imagehash.phash(im)
            return int(str(h), 16)
        except Exception:
            return None

    def _hamming(self, a: int, b: int) -> int:
        try:
            return (a ^ b).bit_count()
        except Exception:
            # Py<3.8 호환
            x = a ^ b
            cnt = 0
            while x:
                x &= x - 1
                cnt += 1
            return cnt

    def _sig(self, path: str) -> Tuple[int,int]:
        st = os.stat(path)
        return int(st.st_mtime), int(st.st_size)

    def _cache_path(self, dir_path: str) -> str:
        key = dir_path.replace(":","_").replace("\\","_").replace("/","_")
        return os.path.join(self._cache_dir, f"{key}.json")

    def build_or_load(self, dir_path: str) -> None:
        cp = self._cache_path(dir_path)
        try:
            if os.path.exists(cp):
                with open(cp, "r", encoding="utf-8") as fh:
                    self._index = json.load(fh)
        except Exception:
            self._index = {}
        for name in os.listdir(dir_path):
            p = os.path.join(dir_path, name)
            if not os.path.isfile(p) or not self._is_image(p):
                continue
            try:
                m, s = self._sig(p)
                rec = self._index.get(p)
                if rec and rec.get("mtime") == m and rec.get("size") == s:
                    continue
                vec = self._vec_image(p)
                if vec is None:
                    continue
                rec: Dict[str, object] = {"vec": vec.tolist(), "mtime": m, "size": s}
                if _HAS_PHASH:
                    ph = self._phash64(p)
                    if ph is not None:
                        rec["phash"] = ph
                self._index[p] = rec
            except Exception:
                pass
        self._index = {k:v for k,v in self._index.items() if os.path.exists(k)}
        try:
            with open(cp, "w", encoding="utf-8") as fh:
                json.dump(self._index, fh)
        except Exception:
            pass

    def similar(self, anchor_path: str, dir_path: str, query_text: str = "", alpha: float = 0.7, top_k: int = 50) -> List[Tuple[str, float]]:
        alpha = float(max(0.0, min(1.0, alpha)))
        self.build_or_load(dir_path)
        a = self._vec_image(anchor_path)
        if a is None:
            return []
        t = self._vec_text(query_text) if query_text else None
        if t is None or a.shape[0] != t.shape[0]:
            q = a
        else:
            q = alpha * a + (1.0 - alpha) * t
        out: List[Tuple[str,float]] = []
        for p, rec in self._index.items():
            if os.path.normcase(p) == os.path.normcase(anchor_path):
                continue
            v = np.asarray(rec.get("vec") or [], dtype=np.float32)
            if v.size == 0:
                continue
            score = _cos(q, v)
            out.append((p, score))
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:top_k]

    def similar_fast(self, anchor_path: str, dir_path: str, top_k: int = 50, preselect: int = 300) -> List[Tuple[str, float]]:
        """pHash로 후보 선별 후 CLIP으로 재랭크하는 2단계 검색."""
        self.build_or_load(dir_path)
        ah = self._phash64(anchor_path)
        cand: List[str] = []
        if ah is not None:
            tmp: List[Tuple[str,int]] = []
            for p, rec in self._index.items():
                if os.path.normcase(p) == os.path.normcase(anchor_path):
                    continue
                ph = rec.get("phash")
                if isinstance(ph, int):
                    d = self._hamming(ah, ph)
                    tmp.append((p, d))
            tmp.sort(key=lambda x: x[1])
            cand = [p for p,_ in tmp[:max(preselect, top_k*5)]]
        if not cand:
            cand = [p for p in self._index.keys() if os.path.normcase(p) != os.path.normcase(anchor_path)]

        a = self._vec_image(anchor_path)
        if a is None:
            return []
        out: List[Tuple[str,float]] = []
        for p in cand:
            v = np.asarray(self._index[p].get("vec") or [], dtype=np.float32)
            if v.size == 0:
                v2 = self._vec_image(p)
                if v2 is None:
                    continue
                self._index[p]["vec"] = v2.tolist()
                v = v2
            out.append((p, _cos(a, v)))
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:top_k]

    def similar_hnsw(self, anchor_path: str, dir_path: str, top_k: int = 50) -> List[Tuple[str, float]]:
        """HNSW ANN 기반 근사 최근접. 대용량 폴더에 적합."""
        if not _HAS_HNSW:
            return self.similar_fast(anchor_path, dir_path, top_k=top_k)
        self.build_or_load(dir_path)
        vecs: List[np.ndarray] = []
        paths: List[str] = []
        for p, rec in self._index.items():
            if os.path.normcase(p) == os.path.normcase(anchor_path):
                continue
            v = np.asarray(rec.get("vec") or [], dtype=np.float32)
            if v.size:
                vecs.append(v)
                paths.append(p)
        if not vecs:
            return []
        X = np.vstack(vecs).astype(np.float32)
        dim = X.shape[1]
        # cosine 유사도를 위해 내적 기반, 벡터 정규화
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
        index = hnswlib.Index(space='ip', dim=dim)
        index.init_index(max_elements=Xn.shape[0], ef_construction=200, M=16)
        index.add_items(Xn)
        index.set_ef(min(200, max(50, top_k*10)))
        q = self._vec_image(anchor_path)
        if q is None:
            return []
        qn = q / (np.linalg.norm(q) + 1e-9)
        labels, dists = index.knn_query(qn, k=min(top_k+5, Xn.shape[0]))
        out: List[Tuple[str,float]] = []
        for lbl, dist in zip(labels[0], dists[0]):
            i = int(lbl)
            score = float(dist)
            if 0 <= i < len(paths):
                out.append((paths[i], score))
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:top_k]

    def similar_auto(self, anchor_path: str, dir_path: str, top_k: int = 50, mode: str = "auto") -> List[Tuple[str,float]]:
        """auto: 파일 수 기준(hnsw>fast>plain), hnsw: ANN, fast: pHash+CLIP, plain: CLIP only"""
        try:
            n = len(self._index) if self._index else len(os.listdir(dir_path))
        except Exception:
            n = 0
        if mode == 'plain':
            return self.similar(anchor_path, dir_path, top_k=top_k)
        if mode == 'fast':
            return self.similar_fast(anchor_path, dir_path, top_k=top_k)
        if mode == 'hnsw' or (mode == 'auto' and n >= 1000 and _HAS_HNSW):
            return self.similar_hnsw(anchor_path, dir_path, top_k=top_k)
        return self.similar_fast(anchor_path, dir_path, top_k=top_k)


