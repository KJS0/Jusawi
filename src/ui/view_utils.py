from __future__ import annotations


def clear_display(viewer) -> None:
    viewer.image_display_area.setPixmap(None)
    viewer.current_image_path = None
    viewer.current_image_index = -1
    viewer.update_window_title()
    viewer.update_status_left()
    viewer.update_status_right()


