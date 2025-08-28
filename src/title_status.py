import os
from .status_utils import human_readable_size, compute_display_bit_depth


def update_window_title(viewer, file_path=None) -> None:
    if file_path and os.path.exists(file_path):
        filename = os.path.basename(file_path)
        viewer.setWindowTitle(f"{filename} - Jusawi")
    else:
        viewer.setWindowTitle("Jusawi")


def update_status_left(viewer) -> None:
    if not viewer.load_successful or not viewer.current_image_path:
        viewer.status_left_label.setText("")
        return
    total = len(viewer.image_files_in_dir)
    idx_disp = viewer.current_image_index + 1 if 0 <= viewer.current_image_index < total else 0
    filename = os.path.basename(viewer.current_image_path)
    try:
        size_bytes = os.path.getsize(viewer.current_image_path)
        size_str = human_readable_size(size_bytes)
    except OSError:
        size_str = "-"
    w = h = depth = 0
    pix = viewer.image_display_area.originalPixmap()
    if pix and not pix.isNull():
        w = pix.width()
        h = pix.height()
        try:
            img = pix.toImage()
            depth = compute_display_bit_depth(img)
        except Exception:
            depth = 0
    dims = f"{w}*{h}*{depth}"
    viewer.status_left_label.setText(f"{idx_disp}/{total} {filename} {size_str} {dims}")


def update_status_right(viewer) -> None:
    percent = int(round(getattr(viewer, "_last_scale", 1.0) * 100))
    viewer.status_right_label.setText(
        f"X:{getattr(viewer, '_last_cursor_x', 0)}, Y:{getattr(viewer, '_last_cursor_y', 0)} {percent}%"
    )


