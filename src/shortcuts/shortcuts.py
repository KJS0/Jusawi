from .shortcuts_manager import apply_shortcuts as _apply_shortcuts


def setup_shortcuts(viewer) -> None:
    _apply_shortcuts(viewer)