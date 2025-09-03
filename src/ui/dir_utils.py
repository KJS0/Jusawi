from __future__ import annotations

import os


def rescan_current_dir(viewer) -> None:
    try:
        dir_path = None
        if viewer.current_image_path:
            d = os.path.dirname(viewer.current_image_path)
            if d and os.path.isdir(d):
                dir_path = d
        if not dir_path and getattr(viewer, "last_open_dir", "") and os.path.isdir(viewer.last_open_dir):
            dir_path = viewer.last_open_dir
        if dir_path:
            viewer.scan_directory(dir_path)
    except Exception:
        pass


