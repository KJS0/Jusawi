import os


def save_last_session(viewer) -> None:
    try:
        last = {
            "file_path": viewer.current_image_path or "",
            "dir_path": os.path.dirname(viewer.current_image_path) if viewer.current_image_path else "",
            "view_mode": getattr(viewer.image_display_area, "_view_mode", getattr(viewer, "_last_view_mode", 'fit')),
            "scale": float(getattr(viewer, "_last_scale", 1.0) or 1.0),
            "fullscreen": bool(viewer.is_fullscreen),
            "window_geometry": viewer.saveGeometry(),
        }
        viewer.settings.setValue("session/last", last)
        viewer.save_settings()
    except Exception:
        pass


def restore_last_session(viewer) -> None:
    try:
        last = viewer.settings.value("session/last", {}, dict)
        if not isinstance(last, dict):
            return
        fpath = last.get("file_path") or ""
        dpath = last.get("dir_path") or ""
        vmode = last.get("view_mode") or 'fit'
        scale = float(last.get("scale") or 1.0)
        if fpath and os.path.isfile(fpath):
            viewer.load_image(fpath, source='restore')
        elif dpath and os.path.isdir(dpath):
            viewer.scan_directory(dpath)
            if 0 <= viewer.current_image_index < len(viewer.image_files_in_dir):
                viewer.load_image(viewer.image_files_in_dir[viewer.current_image_index], source='restore')
        else:
            # 보조 복원: 최근 파일 목록에서 첫 항목 시도
            try:
                recent = viewer.recent_files or []
                if recent:
                    first_path = recent[0].get("path") if isinstance(recent[0], dict) else str(recent[0])
                    if first_path and os.path.isfile(first_path):
                        viewer.load_image(first_path, source='restore')
            except Exception:
                pass
        # 보기 모드/배율 적용
        if vmode == 'fit':
            viewer.image_display_area.fit_to_window()
        elif vmode == 'fit_width':
            viewer.image_display_area.fit_to_width()
        elif vmode == 'fit_height':
            viewer.image_display_area.fit_to_height()
        elif vmode == 'actual':
            viewer.image_display_area.reset_to_100()
        if vmode == 'free' and viewer.image_display_area:
            viewer.image_display_area.set_absolute_scale(scale)
        try:
            geom = last.get("window_geometry")
            if geom:
                viewer.restoreGeometry(geom)
        except Exception:
            pass
    except Exception:
        pass


