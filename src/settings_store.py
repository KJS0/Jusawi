def load_settings(viewer) -> None:
    try:
        viewer.recent_files = viewer.settings.value("recent/files", [], list)
        viewer.recent_folders = viewer.settings.value("recent/folders", [], list)
        if not isinstance(viewer.recent_files, list):
            viewer.recent_files = []
        if not isinstance(viewer.recent_folders, list):
            viewer.recent_folders = []
        viewer.last_open_dir = viewer.settings.value("recent/last_open_dir", "", str)
        if not isinstance(viewer.last_open_dir, str):
            viewer.last_open_dir = ""
        # 회전/저장 정책 관련 기본값 로드
        policy = viewer.settings.value("edit/save_policy", "ask", str)
        viewer._save_policy = policy if policy in ("ask", "overwrite", "save_as") else "ask"
        try:
            viewer._jpeg_quality = int(viewer.settings.value("edit/jpeg_quality", 95))
        except Exception:
            viewer._jpeg_quality = 95
    except Exception:
        viewer.recent_files = []
        viewer.recent_folders = []
        viewer.last_open_dir = ""
        viewer._save_policy = "ask"
        viewer._jpeg_quality = 95


def save_settings(viewer) -> None:
    try:
        viewer.settings.setValue("recent/files", viewer.recent_files)
        viewer.settings.setValue("recent/folders", viewer.recent_folders)
        viewer.settings.setValue("recent/last_open_dir", viewer.last_open_dir)
        viewer.settings.setValue("edit/save_policy", getattr(viewer, "_save_policy", "ask"))
        viewer.settings.setValue("edit/jpeg_quality", int(getattr(viewer, "_jpeg_quality", 95)))
    except Exception:
        pass


