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


