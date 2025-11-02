from __future__ import annotations

import os
from typing import List, Tuple

from .offline_verifier import OfflineVerifierService
from ..utils.logging_setup import get_logger


_log = get_logger("svc.SimilarImageSearch")


class SimilarImageSearchService:
    """
    CLIP 기반 전역 임베딩으로 이미지-이미지 유사도 검색.
    - 범위: 전달받은 파일 목록 내에서만 검색 (비재귀)
    - 캐시: OfflineVerifierService의 임베딩 캐시(SQLite) 재사용
    반환: (path, score[0..1]) 내림차순
    """

    def __init__(self) -> None:
        self._offline = OfflineVerifierService()

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

    def search_similar(
        self,
        query_image: str,
        candidates: List[str],
        top_k: int = 80,
        exclude_self: bool = True,
    ) -> List[Tuple[str, float]]:
        """
        query_image을 기준으로 candidates 내에서 유사 이미지를 찾는다.
        점수는 코사인 유사도를 0..1 범위로 클램프하여 표시한다.
        """
        try:
            if not self._offline.is_ready():
                ok, err = self._offline.prepare()
                if not ok:
                    try:
                        _log.warning("similar_offline_not_ready | err=%s", err)
                    except Exception:
                        pass
                    return []
        except Exception:
            return []

        # 쿼리 임베딩
        try:
            qvec = self._offline._get_or_compute_image_vec(query_image)  # type: ignore[attr-defined]
        except Exception:
            qvec = None
        if not qvec:
            return []

        out: List[Tuple[str, float]] = []
        nc = os.path.normcase
        qn = nc(query_image)
        for p in candidates:
            if not p:
                continue
            if exclude_self and nc(p) == qn:
                continue
            try:
                ivec = self._offline._get_or_compute_image_vec(p)  # type: ignore[attr-defined]
                if not ivec:
                    continue
                c = self._cosine(qvec, ivec)
                # 0..1로 제한(표시 일관성)
                if c < 0.0:
                    c = 0.0
                if c > 1.0:
                    c = 1.0
                out.append((p, float(c)))
            except Exception:
                continue
        out.sort(key=lambda x: x[1], reverse=True)
        if top_k is None or top_k <= 0:
            return out
        return out[: int(top_k)]


