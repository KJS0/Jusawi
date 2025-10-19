import os


def save_last_session(viewer) -> None:
    try:
        last = {
            "file_path": viewer.current_image_path or "",
            "dir_path": os.path.dirname(viewer.current_image_path) if viewer.current_image_path else "",
            "dir_index": int(getattr(viewer, "current_image_index", -1) or -1),
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
        dindex = int(last.get("dir_index") or -1)
        vmode = last.get("view_mode") or 'fit'
        scale = float(last.get("scale") or 1.0)
        # 디렉터리 컨텍스트가 있으면 이를 우선 복원하고 인덱스를 반영
        if dpath and os.path.isdir(dpath):
            viewer.scan_directory(dpath)
            try:
                if 0 <= dindex < len(viewer.image_files_in_dir):
                    viewer.current_image_index = dindex
            except Exception:
                pass
            if 0 <= viewer.current_image_index < len(viewer.image_files_in_dir):
                viewer.load_image(viewer.image_files_in_dir[viewer.current_image_index], source='restore')
        elif fpath and os.path.isfile(fpath):
            # 폴더 정보가 없을 때만 단일 파일 복원
            viewer.load_image(fpath, source='restore')
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
        remember = getattr(viewer, "_remember_last_view_mode", True)
        preferred = getattr(viewer, "_default_view_mode", 'fit')
        mode_to_apply = vmode if remember else preferred
        if mode_to_apply == 'fit':
            viewer.image_display_area.fit_to_window()
        elif mode_to_apply == 'fit_width':
            viewer.image_display_area.fit_to_width()
        elif mode_to_apply == 'fit_height':
            viewer.image_display_area.fit_to_height()
        elif mode_to_apply == 'actual':
            viewer.image_display_area.reset_to_100()
        if remember and vmode == 'free' and viewer.image_display_area:
            viewer.image_display_area.set_absolute_scale(scale)
        # 창 위치/크기 복원은 기본 비활성화 (_restore_window_geometry 가 True일 때만)
        try:
            if bool(getattr(viewer, "_restore_window_geometry", False)):
                geom = last.get("window_geometry")
                if geom:
                    viewer.restoreGeometry(geom)
        except Exception:
            pass
    except Exception:
        pass


