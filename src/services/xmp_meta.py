from __future__ import annotations

import os
from typing import Optional, Dict

try:
    import libxmp  # type: ignore
    from libxmp import XMPFiles, XMPMeta  # type: ignore
except Exception:  # pragma: no cover
    XMPFiles = None  # type: ignore
    XMPMeta = None  # type: ignore


RAW_EXTS = {".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2", ".raf", ".dng", ".srw"}


def _choose_target(path: str) -> str:
    base, ext = os.path.splitext(path)
    if ext.lower() in RAW_EXTS:
        return base + ".xmp"
    return path


def _open_xmp_for_update(target: str):
    if XMPFiles is None:
        raise RuntimeError("python-xmp-toolkit 미설치")
    xf = XMPFiles(file_path=target, open_forupdate=True)
    xmp = xf.get_xmp() or XMPMeta()
    return xf, xmp


def read_rating_label(path: str) -> Dict[str, object]:
    target = _choose_target(path)
    out = {"rating": 0, "flag": "unflagged", "label": None}
    if XMPFiles is None:
        return out
    xf = None
    try:
        xf = XMPFiles(file_path=target, open_forupdate=False)
        xmp = xf.get_xmp()
        if xmp is None:
            return out
        try:
            r = xmp.get_property_int("http://ns.adobe.com/xap/1.0/", "Rating")
            if isinstance(r, int):
                out["rating"] = int(r)
                if r < 0:
                    out["flag"] = "rejected"
        except Exception:
            pass
        try:
            lbl = xmp.get_property("http://ns.adobe.com/xap/1.0/", "Label")
            if lbl:
                s = str(lbl)
                out["label"] = s
                if s.lower() == "green":
                    out["flag"] = "pick"
        except Exception:
            pass
        return out
    except Exception:
        return out
    finally:
        try:
            if xf:
                xf.close_file()
        except Exception:
            pass


def write_rating(path: str, n: int) -> bool:
    target = _choose_target(path)
    xf = None
    try:
        xf, xmp = _open_xmp_for_update(target)
        xmp.set_property_int("http://ns.adobe.com/xap/1.0/", "Rating", int(n))
        xf.put_xmp(xmp)
        xf.close_file()
        return True
    except Exception:
        try:
            if xf:
                xf.close_file()
        except Exception:
            pass
        return False


def write_label(path: str, label: Optional[str]) -> bool:
    target = _choose_target(path)
    xf = None
    try:
        xf, xmp = _open_xmp_for_update(target)
        if label:
            xmp.set_property("http://ns.adobe.com/xap/1.0/", "Label", str(label))
        else:
            try:
                xmp.delete_property("http://ns.adobe.com/xap/1.0/", "Label")
            except Exception:
                pass
        xf.put_xmp(xmp)
        xf.close_file()
        return True
    except Exception:
        try:
            if xf:
                xf.close_file()
        except Exception:
            pass
        return False


def set_flag_pick(path: str, pick: bool) -> bool:
    # pick: Label="Green" (Adobe 생태계 호환)
    return write_label(path, "Green" if pick else None)


def set_flag_reject(path: str, reject: bool) -> bool:
    # reject: Rating=-1 (Adobe 생태계 호환)
    return write_rating(path, -1 if reject else 0)


