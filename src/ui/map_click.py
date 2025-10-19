from __future__ import annotations

from PyQt6.QtCore import QUrl  # type: ignore[import]
from PyQt6.QtGui import QDesktopServices  # type: ignore[import]


def handle_mouse_press(owner, event) -> bool:
    try:
        if event is not None and getattr(owner, "info_map_label", None) is not None:
            if owner.info_map_label.isVisible() and owner.info_panel.isVisible():
                if owner.info_map_label.rect().contains(owner.info_map_label.mapFrom(owner, event.position().toPoint())):
                    link = owner.info_map_label.toolTip() if hasattr(owner.info_map_label, 'toolTip') else ""
                    if link and isinstance(link, str) and link.startswith("http"):
                        QDesktopServices.openUrl(QUrl(link))
                        return True
    except Exception:
        return False
    return False


