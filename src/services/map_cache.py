from __future__ import annotations

import os, hashlib, threading
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt6.QtGui import QPixmap

_cache_mem: dict[str, QPixmap] = {}
_lock = threading.Lock()

def _cache_dir() -> str:
    base = os.path.join(os.path.expanduser("~"), ".jusawi", "maps")
    os.makedirs(base, exist_ok=True)
    return base

def _key(lat: float, lon: float, w: int, h: int, zoom: int) -> str:
    s = f"{lat:.6f},{lon:.6f}|{w}x{h}|z{zoom}"
    return hashlib.sha1(s.encode()).hexdigest()

def get_cached(lat: float, lon: float, w: int, h: int, zoom: int) -> Optional[QPixmap]:
    k = _key(lat, lon, w, h, zoom)
    with _lock:
        pm = _cache_mem.get(k)
        if pm and not pm.isNull():
            return pm
    p = os.path.join(_cache_dir(), f"{k}.png")
    if os.path.exists(p):
        pm = QPixmap(p)
        if not pm.isNull():
            with _lock:
                _cache_mem[k] = pm
            return pm
    return None

def put_cached(lat: float, lon: float, w: int, h: int, zoom: int, pm: QPixmap) -> None:
    if pm.isNull():
        return
    k = _key(lat, lon, w, h, zoom)
    with _lock:
        _cache_mem[k] = pm
    p = os.path.join(_cache_dir(), f"{k}.png")
    try:
        pm.save(p, "PNG")
    except Exception:
        pass

class MapFetchTask(QRunnable):
    def __init__(self, lat: float, lon: float, w: int, h: int, zoom: int, token: int, receiver: QObject, signal_name: str):
        super().__init__()
        self.lat, self.lon, self.w, self.h, self.zoom, self.token = lat, lon, w, h, zoom, token
        self.receiver, self.signal_name = receiver, signal_name

    def run(self):
        pm = get_cached(self.lat, self.lon, self.w, self.h, self.zoom)
        if pm is None:
            try:
                from .geocoding import get_google_static_map_png  # type: ignore
                data = get_google_static_map_png(self.lat, self.lon, width=self.w, height=self.h, zoom=self.zoom)
                if data:
                    pm2 = QPixmap()
                    if pm2.loadFromData(bytes(data)):
                        put_cached(self.lat, self.lon, self.w, self.h, self.zoom, pm2)
                        pm = pm2
            except Exception:
                pm = None
        try:
            sig = getattr(self.receiver, self.signal_name)
            sig.emit(self.token, pm if pm else QPixmap())
        except Exception:
            pass

def submit_fetch(lat: float, lon: float, w: int, h: int, zoom: int, token: int, receiver: QObject, signal_name: str):
    QThreadPool.globalInstance().start(MapFetchTask(lat, lon, w, h, zoom, token, receiver, signal_name))


