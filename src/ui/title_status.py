import os
from ..utils.status_utils import human_readable_size, compute_display_bit_depth, describe_colorspace


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
    # 자연 해상도 우선 표기(다운샘플 표시 중에도 원본 해상도로 표기)
    try:
        nat_w = int(getattr(viewer.image_display_area, "_natural_width", 0) or 0)
        nat_h = int(getattr(viewer.image_display_area, "_natural_height", 0) or 0)
    except Exception:
        nat_w = nat_h = 0
    if nat_w > 0 and nat_h > 0:
        w, h = nat_w, nat_h
        try:
            # 비트 심도는 현재 픽스맵으로 추정
            if pix and not pix.isNull():
                img = pix.toImage()
                depth = compute_display_bit_depth(img)
        except Exception:
            depth = 0
    elif pix and not pix.isNull():
        w = pix.width()
        h = pix.height()
        try:
            img = pix.toImage()
            depth = compute_display_bit_depth(img)
        except Exception:
            depth = 0
    dims = f"{w}*{h}*{depth}"
    # 색공간 표기 추가: sRGB/기타/미상
    cs = ""
    try:
        if pix and not pix.isNull():
            img = pix.toImage()
            cs = describe_colorspace(img)
    except Exception:
        cs = ""
    # 상세 표시 옵션: 프로파일명/비트뎁스
    show_detail = bool(getattr(viewer, "_statusbar_show_profile_details", False))
    cs_disp = f" [{cs}]" if cs else ""
    if show_detail and pix and not pix.isNull():
        try:
            img2 = pix.toImage()
            name = getattr(img2.colorSpace(), 'description', lambda: '')() or cs
            depth2 = compute_display_bit_depth(img2)
            cs_disp = f" [{name or cs}/{depth2}b]"
        except Exception:
            pass
    viewer.status_left_label.setText(f"{idx_disp}/{total} {filename} {size_str} {dims}{cs_disp}")
    # 현재 표시가 썸네일이면 원본 업그레이드를 예약(정렬/인덱스 변동 시에도 보장)
    try:
        if getattr(viewer, "load_successful", False) and getattr(viewer, "current_image_path", None):
            if not viewer._is_current_file_animation() and not getattr(viewer, "_movie", None):
                need_upgrade = False
                fullimg = getattr(viewer, "_fullres_image", None)
                if fullimg is None or fullimg.isNull():
                    need_upgrade = True
                else:
                    try:
                        cur_pix = viewer.image_display_area.originalPixmap()
                        if cur_pix and not cur_pix.isNull():
                            if cur_pix.width() < fullimg.width() or cur_pix.height() < fullimg.height():
                                need_upgrade = True
                    except Exception:
                        pass
                if need_upgrade and not bool(getattr(viewer, "_pause_auto_upgrade", False)):
                    try:
                        if viewer._fullres_upgrade_timer.isActive():
                            viewer._fullres_upgrade_timer.stop()
                        delay = int(getattr(viewer, "_fullres_upgrade_delay_ms", 120))
                        viewer._fullres_upgrade_timer.start(max(0, delay))
                    except Exception:
                        pass
    except Exception:
        pass


def update_status_right(viewer) -> None:
    percent = int(round(getattr(viewer, "_last_scale", 1.0) * 100))
    viewer.status_right_label.setText(
        f"X:{getattr(viewer, '_last_cursor_x', 0)}, Y:{getattr(viewer, '_last_cursor_y', 0)} {percent}%"
    )


