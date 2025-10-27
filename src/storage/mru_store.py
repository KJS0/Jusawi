import os


def normalize_path(p: str) -> str:
    try:
        return os.path.normcase(os.path.normpath(p))
    except Exception:
        return p


def update_mru(mru_list: list, path: str, max_items: int = 10) -> list:
    norm = normalize_path(path)
    filtered = []
    seen = set()
    for it in mru_list:
        ip = it.get("path", "") if isinstance(it, dict) else str(it)
        key = normalize_path(ip)
        if key and key != norm and key not in seen:
            filtered.append({"path": ip})
            seen.add(key)
    filtered.insert(0, {"path": path})
    return filtered[:max_items]



def _split_patterns(raw: str) -> list[str]:
    parts: list[str] = []
    try:
        for p in (raw or "").split(";"):
            s = p.strip()
            if s:
                parts.append(s)
    except Exception:
        pass
    return parts


def _matches_any(path: str, patterns: list[str]) -> bool:
    try:
        npc = normalize_path(path)
        for p in patterns:
            pp = normalize_path(p)
            if not pp:
                continue
            # 절대 경로인 경우: 시작 경로 매치, 그 외: 부분 문자열 매치
            try:
                if os.path.isabs(pp):
                    if npc.startswith(pp):
                        return True
                else:
                    if pp in npc:
                        return True
            except Exception:
                # os.path.isabs 실패 시 부분 문자열 매치로 폴백
                if pp in npc:
                    return True
    except Exception:
        return False
    return False


def process_mru(
    mru_list: list,
    *,
    max_items: int = 10,
    exclude_patterns: str | list[str] = "",
    auto_prune_missing: bool = True,
    is_folder: bool = False,
) -> list:
    try:
        # 표준화된 아이템 리스트로 변환
        items = []
        for it in mru_list or []:
            if isinstance(it, dict):
                p = it.get("path", "")
            else:
                p = str(it)
            if p:
                items.append({"path": p})

        # 제외 규칙 적용
        if isinstance(exclude_patterns, str):
            excl = _split_patterns(exclude_patterns)
        else:
            excl = list(exclude_patterns or [])
        if excl:
            items = [it for it in items if not _matches_any(it.get("path", ""), excl)]

        # 존재하지 않는 항목 제거(옵션)
        if auto_prune_missing:
            filtered = []
            for it in items:
                p = it.get("path", "")
                if not p:
                    continue
                if is_folder:
                    if os.path.isdir(p):
                        filtered.append(it)
                else:
                    if os.path.isfile(p):
                        filtered.append(it)
            items = filtered

        # 핀 고정 기능 제거됨

        # 최대 개수 제한
        items = items[: max(1, int(max_items))]
        return items
    except Exception:
        return (mru_list or [])[: max_items]