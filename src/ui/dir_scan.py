from __future__ import annotations

import os


def scan_directory(owner, dir_path: str):
    try:
        owner.log.info("scan_dir_start | dir=%s", os.path.basename(dir_path or ""))
    except Exception:
        pass
    try:
        owner._last_scanned_dir = dir_path or ""
    except Exception:
        pass
    owner.image_files_in_dir, owner.current_image_index = owner.image_service.scan_directory(dir_path, owner.current_image_path)
    try:
        if (owner.current_image_index is None or owner.current_image_index < 0) and owner.image_files_in_dir:
            owner.current_image_index = 0
    except Exception:
        if owner.image_files_in_dir:
            owner.current_image_index = 0
    owner.update_button_states()
    owner.update_status_left()
    try:
        owner.log.info("scan_dir_done | dir=%s | count=%d | cur=%d", os.path.basename(dir_path or ""), len(owner.image_files_in_dir), int(owner.current_image_index))
    except Exception:
        pass
    try:
        cur = int(owner.current_image_index) if owner.current_image_index is not None else -1
        if hasattr(owner, 'filmstrip') and owner.filmstrip is not None:
            owner.filmstrip.set_items(owner.image_files_in_dir or [], cur)
    except Exception:
        pass
    try:
        if owner.load_successful and owner.current_image_path and not owner._is_current_file_animation():
            need_upgrade = False
            if getattr(owner, "_fullres_image", None) is None or owner._fullres_image.isNull():
                need_upgrade = True
            else:
                cur_pix = owner.image_display_area.originalPixmap()
                if cur_pix and not cur_pix.isNull():
                    if cur_pix.width() < owner._fullres_image.width() or cur_pix.height() < owner._fullres_image.height():
                        need_upgrade = True
            if need_upgrade:
                if owner._fullres_upgrade_timer.isActive():
                    owner._fullres_upgrade_timer.stop()
                owner._fullres_upgrade_timer.start(120)
    except Exception:
        pass


def rescan_current_dir(owner):
    from .dir_utils import rescan_current_dir as _rescan
    return _rescan(owner)


