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
        policy = viewer.settings.value("edit/save_policy", "discard", str)
        # 'ask'도 기본적으로 무시하고 'discard'로 동작하도록 강제
        if policy in ("overwrite", "save_as"):
            viewer._save_policy = policy
        else:
            viewer._save_policy = "discard"
        try:
            viewer._jpeg_quality = int(viewer.settings.value("edit/jpeg_quality", 95))
        except Exception:
            viewer._jpeg_quality = 95
        # UI 환경 설정 로드
        theme = viewer.settings.value("ui/theme", "dark", str)
        viewer._theme = theme if theme in ("dark", "light", "system") else "dark"
        margins_str = viewer.settings.value("ui/margins", "5,5,5,5", str)
        try:
            parts = [int(p.strip()) for p in str(margins_str).split(",")]
            if len(parts) == 4:
                viewer._ui_margins = tuple(parts)
            else:
                viewer._ui_margins = (5, 5, 5, 5)
        except Exception:
            viewer._ui_margins = (5, 5, 5, 5)
        try:
            viewer._ui_spacing = int(viewer.settings.value("ui/spacing", 6))
        except Exception:
            viewer._ui_spacing = 6
        dvm = viewer.settings.value("ui/default_view_mode", "fit", str)
        viewer._default_view_mode = dvm if dvm in ("fit", "fit_width", "fit_height", "actual") else "fit"
        try:
            viewer._remember_last_view_mode = bool(viewer.settings.value("ui/remember_last_view_mode", True, bool))
        except Exception:
            viewer._remember_last_view_mode = True
    except Exception:
        viewer.recent_files = []
        viewer.recent_folders = []
        viewer.last_open_dir = ""
        viewer._save_policy = "ask"
        viewer._jpeg_quality = 95
        viewer._theme = "dark"
        viewer._ui_margins = (5, 5, 5, 5)
        viewer._ui_spacing = 6
        viewer._default_view_mode = "fit"
        viewer._remember_last_view_mode = True


def save_settings(viewer) -> None:
    try:
        viewer.settings.setValue("recent/files", viewer.recent_files)
        viewer.settings.setValue("recent/folders", viewer.recent_folders)
        viewer.settings.setValue("recent/last_open_dir", viewer.last_open_dir)
        viewer.settings.setValue("edit/save_policy", getattr(viewer, "_save_policy", "discard"))
        viewer.settings.setValue("edit/jpeg_quality", int(getattr(viewer, "_jpeg_quality", 95)))
        # UI 환경 설정 저장
        viewer.settings.setValue("ui/theme", getattr(viewer, "_theme", "dark"))
        m = getattr(viewer, "_ui_margins", (5, 5, 5, 5))
        try:
            m_str = ",".join(str(int(x)) for x in m)
        except Exception:
            m_str = "5,5,5,5"
        viewer.settings.setValue("ui/margins", m_str)
        viewer.settings.setValue("ui/spacing", int(getattr(viewer, "_ui_spacing", 6)))
        viewer.settings.setValue("ui/default_view_mode", getattr(viewer, "_default_view_mode", "fit"))
        viewer.settings.setValue("ui/remember_last_view_mode", bool(getattr(viewer, "_remember_last_view_mode", True)))
    except Exception:
        pass


