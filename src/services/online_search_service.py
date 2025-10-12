from __future__ import annotations

import os
import sqlite3
import json
from typing import List, Tuple, Optional, Dict, Any

from ..utils.logging_setup import get_logger

_log = get_logger("svc.OnlineSearch")


def _read_vec(b: bytes) -> List[float]:
    try:
        s = b.decode("utf-8")
        return [float(x) for x in s.split(",") if x]
    except Exception:
        return []


def _write_vec(vec: List[float]) -> bytes:
    return (",".join(f"{x:.7f}" for x in vec)).encode("utf-8")


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


def _build_doc_for_image(path: str) -> str:
    """이미지의 파일명/폴더/가벼운 EXIF 요약을 이용해 텍스트 문서를 구성."""
    try:
        import os as _os
        base = _os.path.basename(path)
        parent = _os.path.basename(_os.path.dirname(path))
        parts = [f"file: {base}", f"folder: {parent}"]
    except Exception:
        parts = [f"file: {path}"]
    # EXIF 요약(가벼움)
    try:
        from .ai_analysis_service import _extract_exif_summary  # type: ignore
        ex = _extract_exif_summary(path) or {}
        if ex:
            ex_lines = []
            for k in [
                "make",
                "model",
                "lens",
                "aperture",
                "shutter",
                "iso",
                "focal_length_mm",
                "focal_length_35mm_eq_mm",
                "datetime_original",
            ]:
                v = ex.get(k)
                if v is not None and str(v).strip() != "":
                    ex_lines.append(f"{k}: {v}")
            if ex_lines:
                parts.append("exif: " + "; ".join(ex_lines))
    except Exception:
        pass
    return " | ".join(parts)


class OnlineEmbeddingIndex:
    """OpenAI 임베딩으로 로컬 이미지 컬렉션을 색인/검색.

    - 임베딩 모델: env EMBED_MODEL (기본: text-embedding-3-small)
    - DB: ~/.jusawi/online_embed.sqlite3
    - 벡터 저장 형식: CSV float 문자열(bytes)
    """

    def __init__(self):
        base_dir = os.path.join(os.path.expanduser("~"), ".jusawi")
        try:
            os.makedirs(base_dir, exist_ok=True)
        except Exception:
            pass
        self._db_path = os.path.join(base_dir, "online_embed.sqlite3")
        self._model = os.getenv("EMBED_MODEL", "text-embedding-3-small").strip() or "text-embedding-3-small"
        self._api_key = os.getenv("OPENAI_API_KEY")
        self._ensure_db()

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
                    vec BLOB,
                    meta TEXT
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_vectors_model ON vectors(model)")
            con.commit()
        finally:
            con.close()

    def _get_mtime(self, path: str) -> int:
        try:
            return int(os.path.getmtime(path))
        except Exception:
            return 0

    def _embed_text_batch(self, texts: List[str]) -> List[List[float]]:
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY 없음")
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:
            raise RuntimeError(f"openai SDK 로드 실패: {e}")
        client = OpenAI(api_key=self._api_key)
        # OpenAI Embeddings API: 최대 입력 길이에 주의(안전하게 batch로 처리)
        resp = client.embeddings.create(model=self._model, input=texts)
        out: List[List[float]] = []
        for item in resp.data:
            out.append(list(item.embedding))
        return out

    def ensure_index(self, image_paths: List[str], progress_cb=None) -> int:
        """경로 목록에 대해 누락/구버전 임베딩을 생성해 저장. 반환: 새로 생성한 개수."""
        pending: List[Tuple[str, str, int]] = []  # (path, doc, mtime)
        con = sqlite3.connect(self._db_path)
        try:
            cur = con.cursor()
            for p in image_paths:
                mt = self._get_mtime(p)
                try:
                    cur.execute("SELECT mtime, model FROM vectors WHERE path=?", (p,))
                    row = cur.fetchone()
                except Exception:
                    row = None
                need = True
                if row is not None:
                    try:
                        prev_mtime = int(row[0])
                        prev_model = str(row[1] or "")
                        if prev_mtime == mt and prev_model == self._model:
                            need = False
                        else:
                            need = True
                    except Exception:
                        need = True
                if need:
                    doc = _build_doc_for_image(p)
                    pending.append((p, doc, mt))
        finally:
            con.close()

        created = 0
        if not pending:
            return created
        # 배치 단위로 임베딩
        B = int(os.getenv("EMBED_BATCH", "64") or 64)
        i = 0
        while i < len(pending):
            chunk = pending[i : i + B]
            texts = [d for (_, d, __) in chunk]
            if progress_cb:
                try:
                    progress_cb(min(90, int(100 * (i / max(1, len(pending))))), f"임베딩 {i+1}-{min(i+B, len(pending))}/{len(pending)}")
                except Exception:
                    pass
            vecs = self._embed_text_batch(texts)
            con = sqlite3.connect(self._db_path)
            try:
                cur = con.cursor()
                for (path, doc, mt), vec in zip(chunk, vecs):
                    try:
                        cur.execute(
                            "INSERT INTO vectors(path, mtime, model, dim, vec, meta) VALUES(?,?,?,?,?,?) "
                            "ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, model=excluded.model, dim=excluded.dim, vec=excluded.vec, meta=excluded.meta",
                            (path, mt, self._model, len(vec), _write_vec(vec), json.dumps({"doc": doc}, ensure_ascii=False)),
                        )
                        created += 1
                    except Exception:
                        pass
                con.commit()
            finally:
                con.close()
            i += B
        return created

    def _load_all_vectors(self, image_paths: List[str]) -> List[Tuple[str, List[float]]]:
        con = sqlite3.connect(self._db_path)
        out: List[Tuple[str, List[float]]] = []
        try:
            cur = con.cursor()
            qmarks = ",".join(["?"] * len(image_paths)) if image_paths else ""
            if not qmarks:
                return []
            cur.execute(f"SELECT path, dim, vec FROM vectors WHERE path IN ({qmarks}) AND model=?", (*image_paths, self._model))
            for row in cur.fetchall():
                path = str(row[0])
                # dim = int(row[1])  # 미사용
                vec = _read_vec(row[2])
                if vec:
                    out.append((path, vec))
        except Exception:
            pass
        finally:
            con.close()
        return out

    def search(self,
               image_paths: List[str],
               query_text: str,
               top_k: int = 50,
               verify_top_n: int = 20,
               verify_mode: str = "normal",
               progress_cb=None) -> List[Tuple[str, float]]:
        if not query_text.strip():
            return []
        if progress_cb:
            try:
                progress_cb(5, "색인 확인")
            except Exception:
                pass
        # 임베딩 미사용 모드: 사진만으로 재검증 점수로 순위화 (기본 활성화)
        no_embed = os.getenv("SEARCH_NO_EMBEDDING", "1") == "1"
        # 검증 통과 항목만 반환(엄격 모드) 기본 활성화
        strict_only = os.getenv("SEARCH_VERIFY_STRICT_ONLY", "1") == "1"
        # 검증 모드 기본값: strict
        vm = (verify_mode or "").strip().lower()
        if vm not in ("loose", "normal", "strict"):
            try:
                vm = (os.getenv("SEARCH_VERIFY_MODE", "strict") or "strict").lower()
            except Exception:
                vm = "strict"
        if no_embed:
            if progress_cb:
                try:
                    progress_cb(20, "임베딩 생략: 후보 수집")
                except Exception:
                    pass
            try:
                verify_cap = int(os.getenv("SEARCH_VERIFY_MAX", "200") or 200)
            except Exception:
                verify_cap = 200
            verify_cap = max(1, verify_cap)
            cands = list(image_paths)[:verify_cap]
            scored: List[Tuple[str, float]] = [(p, 0.0) for p in cands]
            top_k = len(scored)
            verify_top_n = len(scored)
        else:
            try:
                self.ensure_index(image_paths, progress_cb=progress_cb)
            except Exception as e:
                try:
                    _log.warning("ensure_index_fail | err=%s", str(e))
                except Exception:
                    pass
            if progress_cb:
                try:
                    progress_cb(25, "질의 임베딩")
                except Exception:
                    pass
            qvec = self._embed_text_batch([query_text])[0]
            if progress_cb:
                try:
                    progress_cb(45, "코사인 유사도 계산")
                except Exception:
                    pass
            items = self._load_all_vectors(image_paths)
            scored = []
            for path, ivec in items:
                c = _cosine(qvec, ivec)
                if c > 0:
                    scored.append((path, float(c)))
            scored.sort(key=lambda x: x[1], reverse=True)
            scored = scored[: max(1, int(top_k))]

        # gpt-5-nano 재검증 (병렬) + 점수 블렌딩
        if verify_top_n > 0 and scored:
            if progress_cb:
                try:
                    progress_cb(65, "후보 재검증")
                except Exception:
                    pass
            try:
                from .verifier_service import VerifierService  # type: ignore
                verifier = VerifierService()
                verified: List[Tuple[str, float]] = []
                n = min(int(verify_top_n), len(scored))
                # 병렬 워커 수 설정
                try:
                    workers = int(os.getenv("SEARCH_VERIFY_WORKERS", "16") or 16)
                except Exception:
                    workers = 16
                workers = max(1, min(64, workers))
                # 병렬 실행
                try:
                    import concurrent.futures as _fut
                except Exception:
                    _fut = None  # type: ignore

                tasks: List[Tuple[int, str]] = [(i, scored[i][0]) for i in range(n)]
                if _fut is not None and workers > 1:
                    with _fut.ThreadPoolExecutor(max_workers=workers) as ex:
                        fut_to_idx = {
                            ex.submit(verifier.verify, path, query_text): idx for idx, path in tasks
                        }
                        done_cnt = 0
                        for fut in _fut.as_completed(fut_to_idx):
                            idx = fut_to_idx[fut]
                            path = scored[idx][0]
                            try:
                                res = fut.result()
                                conf = float(res.get("confidence", 0.0))
                                if verifier.pass_threshold(conf, vm):
                                    verified.append((path, conf))
                            except Exception:
                                pass
                            done_cnt += 1
                            if progress_cb:
                                try:
                                    base = 65
                                    span = 25
                                    progress_cb(base + int(span * (done_cnt / max(1, n))), "재검증 진행 중")
                                except Exception:
                                    pass
                else:
                    # 폴백: 순차 실행
                    for i, path in tasks:
                        res = verifier.verify(path, query_text)
                        conf = float(res.get("confidence", 0.0))
                        if verifier.pass_threshold(conf, vm):
                            verified.append((path, conf))
                        if progress_cb:
                            try:
                                base = 65
                                span = 25
                                progress_cb(base + int(span * ((i + 1) / max(1, n))), "재검증 진행 중")
                            except Exception:
                                pass

                if verified:
                    if no_embed:
                        # 임베딩 없이 신뢰도만으로 정렬하여 반환(검증 통과분만)
                        verified.sort(key=lambda x: x[1], reverse=True)
                        return verified
                    # 블렌딩: alpha*conf + (1-alpha)*embed_score
                    try:
                        alpha = float(os.getenv("SEARCH_BLEND_ALPHA", "0.7") or 0.7)
                    except Exception:
                        alpha = 0.7
                    alpha = max(0.0, min(1.0, alpha))
                    embed_map = {p: s for p, s in scored[:n]}
                    blended: List[Tuple[str, float]] = []
                    for p, conf in verified:
                        es = float(embed_map.get(p, 0.0))
                        blended.append((p, float(alpha * conf + (1.0 - alpha) * es)))
                    blended.sort(key=lambda x: x[1], reverse=True)
                    # strict-only면 tail 제거(검증 통과분만 반환)
                    if strict_only:
                        return blended
                    # 기본: 뒤쪽 꼬리는 원래 점수로 유지
                    return blended + scored[n:]
            except Exception as e:
                try:
                    _log.warning("verify_fail | err=%s", str(e))
                except Exception:
                    pass
        return scored


