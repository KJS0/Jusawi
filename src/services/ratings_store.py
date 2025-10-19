from __future__ import annotations

import os
import sqlite3
from typing import Optional, Tuple, Dict

DB_DIR = os.path.join(os.path.expanduser("~"), ".jusawi")
DB_PATH = os.path.join(DB_DIR, "ratings.sqlite3")


def _ensure_db() -> None:
    os.makedirs(DB_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                path TEXT PRIMARY KEY,
                mtime INTEGER,
                rating INTEGER DEFAULT 0,
                label TEXT,
                flag TEXT DEFAULT 'unflagged'
            )
            """
        )
        con.commit()
    finally:
        con.close()


def upsert_image(path: str, mtime: int, rating: int = 0, label: Optional[str] = None, flag: str = "unflagged") -> None:
    _ensure_db()
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO images(path, mtime, rating, label, flag)
            VALUES(?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
                mtime=excluded.mtime,
                rating=excluded.rating,
                label=excluded.label,
                flag=excluded.flag
            """,
            (path, int(mtime), int(rating), label, flag)
        )
        con.commit()
    finally:
        con.close()


def get_image(path: str) -> Optional[Dict[str, object]]:
    _ensure_db()
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("SELECT path, mtime, rating, label, flag FROM images WHERE path=?", (path,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "path": str(row[0]),
            "mtime": int(row[1]),
            "rating": int(row[2]) if row[2] is not None else 0,
            "label": row[3],
            "flag": str(row[4]) if row[4] else "unflagged",
        }
    finally:
        con.close()


