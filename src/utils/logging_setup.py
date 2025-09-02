import os
import sys
import uuid
import logging
import logging.handlers
import queue
from typing import Optional
import zipfile
import datetime
import subprocess
import threading
import atexit

_SESSION_ID = uuid.uuid4().hex[:8]
_listener: logging.handlers.QueueListener | None = None
_error_snapshot_done = False


class _SessionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        if not hasattr(record, "session_id"):
            record.session_id = _SESSION_ID
        try:
            _maybe_snapshot_on_error(record)
        except Exception:
            pass
        return True


def _default_log_dir() -> str:
    try:
        if sys.platform == "win32":
            base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
            path = os.path.join(base, "Jusawi", "logs")
        else:
            base = os.getenv("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
            path = os.path.join(base, "Jusawi", "logs")
        os.makedirs(path, exist_ok=True)
        return path
    except Exception:
        return os.getcwd()


def setup_logging(level: str = "INFO", log_dir: Optional[str] = None, json: bool = False) -> None:
    """Initialize app-wide logging with rotating file handler and queue listener."""
    global _listener
    if logging.getLogger().handlers:
        set_level(level)
        return

    lvl = getattr(logging, str(level).upper(), logging.INFO)
    q: "queue.Queue[logging.LogRecord]" = queue.Queue(maxsize=10000)
    qh = logging.handlers.QueueHandler(q)
    qh.addFilter(_SessionFilter())

    root = logging.getLogger()
    root.setLevel(lvl)
    root.addHandler(qh)

    log_dir = log_dir or _default_log_dir()
    log_path = os.path.join(log_dir, "app.log")

    fh = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )
    if json:
        fmt = logging.Formatter('{"ts":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","sid":"%(session_id)s","msg":"%(message)s"}')
    else:
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | sid=%(session_id)s | %(message)s")
    fh.setFormatter(fmt)

    sh = logging.StreamHandler(stream=sys.stderr)
    sh.setLevel(lvl)
    sh.setFormatter(fmt)

    _listener = logging.handlers.QueueListener(q, fh, sh, respect_handler_level=True)
    _listener.start()

    # optional: exit snapshot
    try:
        if str(os.getenv("JUSAWI_LOG_SNAPSHOT_ON_EXIT", "0")).strip() in ("1", "true", "True"):
            atexit.register(_export_snapshot_background, suffix="exit")
    except Exception:
        pass


def shutdown_logging() -> None:
    global _listener
    try:
        if _listener:
            _listener.stop()
    except Exception:
        pass


def set_level(level: str) -> None:
    try:
        lvl = getattr(logging, str(level).upper(), logging.INFO)
        logging.getLogger().setLevel(lvl)
    except Exception:
        pass


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def get_log_dir() -> str:
    """현재 사용 중인 로그 디렉터리 반환."""
    return _default_log_dir()


def export_logs_zip(dest_zip_path: str) -> tuple[bool, str]:
    """로그 디렉터리의 파일들을 ZIP으로 묶어 저장.
    반환: (성공, 오류 메시지)
    """
    try:
        log_dir = get_log_dir()
        if not os.path.isdir(log_dir):
            return False, "로그 디렉터리를 찾을 수 없습니다."
        with zipfile.ZipFile(dest_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in os.listdir(log_dir):
                path = os.path.join(log_dir, name)
                if os.path.isfile(path):
                    zf.write(path, arcname=name)
            # 메타정보 파일 포함(세션ID 포함)
            try:
                meta_name = f"meta_{_SESSION_ID}.txt"
                info = f"session_id={_SESSION_ID}\ncreated_utc={datetime.datetime.utcnow().isoformat()}\n"
                zf.writestr(meta_name, info)
            except Exception:
                pass
        return True, ""
    except Exception as e:
        return False, str(e)


def suggest_logs_zip_name() -> str:
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"jusawi_logs_{ts}.zip"


def open_logs_folder() -> tuple[bool, str]:
    """OS 기본 탐색기로 로그 폴더 열기."""
    try:
        path = get_log_dir()
        if not os.path.isdir(path):
            return False, "로그 디렉터리를 찾을 수 없습니다."
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True, ""
    except Exception as e:
        return False, str(e)


# --- 자동 스냅샷 로직 ------------------------------------------------------

def _snapshot_dir() -> str:
    d = os.path.join(get_log_dir(), "snapshots")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _snapshot_path(suffix: str) -> str:
    base = suggest_logs_zip_name().replace(".zip", f"_{suffix}.zip")
    return os.path.join(_snapshot_dir(), base)


def _export_snapshot_background(suffix: str) -> None:
    try:
        dest = _snapshot_path(suffix)
        export_logs_zip(dest)
    except Exception:
        pass


def _maybe_snapshot_on_error(record: logging.LogRecord) -> None:
    global _error_snapshot_done
    if _error_snapshot_done:
        return
    # on first ERROR or higher, create a background snapshot if enabled (default: on)
    try:
        enabled = os.getenv("JUSAWI_LOG_SNAPSHOT_ON_ERROR")
        if enabled is None:
            # 기본 활성화
            should = True
        else:
            should = str(enabled).strip() in ("1", "true", "True")
    except Exception:
        should = True
    if not should:
        return
    if getattr(record, "levelno", logging.INFO) >= logging.ERROR:
        _error_snapshot_done = True
        t = threading.Thread(target=_export_snapshot_background, args=("error",), daemon=True)
        t.start()



