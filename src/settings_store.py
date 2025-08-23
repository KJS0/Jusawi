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
    except Exception:
        viewer.recent_files = []
        viewer.recent_folders = []
        viewer.last_open_dir = ""


def save_settings(viewer) -> None:
    try:
        viewer.settings.setValue("recent/files", viewer.recent_files)
        viewer.settings.setValue("recent/folders", viewer.recent_folders)
        viewer.settings.setValue("recent/last_open_dir", viewer.last_open_dir)
    except Exception:
        pass


