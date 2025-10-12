from __future__ import annotations

import os
from typing import TYPE_CHECKING
from PyQt6.QtGui import QPixmap, QMovie  # type: ignore[import]

from ..storage.mru_store import update_mru

if TYPE_CHECKING:
    from .main_window import JusawiViewer


def apply_loaded_image(viewer: "JusawiViewer", path: str, img, source: str) -> None:
    pixmap = QPixmap.fromImage(img)
    viewer.image_display_area.setPixmap(pixmap)
    try:
        viewer._fullres_image = img
        try:
            viewer.image_display_area._natural_width = int(img.width())
            viewer.image_display_area._natural_height = int(img.height())
        except Exception:
            pass
    except Exception:
        viewer._fullres_image = None
    try:
        if getattr(viewer, "_movie", None):
            try:
                viewer._movie.stop()
            except Exception:
                pass
            viewer._movie.deleteLater()
    except Exception:
        pass
    viewer._movie = None
    try:
        is_anim, frame_count = viewer.image_service.probe_animation(path)
        viewer.image_display_area.set_animation_state(is_anim, current_index=0, total_frames=frame_count)
        if is_anim:
            try:
                mv = QMovie(path)
                mv.setCacheMode(QMovie.CacheMode.CacheAll)
                try:
                    mv.jumpToFrame(0)
                except Exception:
                    pass
                mv.frameChanged.connect(viewer._on_movie_frame)
                viewer._movie = mv
                try:
                    viewer._anim_timer.stop()
                except Exception:
                    pass
                try:
                    viewer._movie.start()
                    viewer._anim_is_playing = True
                except Exception:
                    viewer._anim_is_playing = False
            except Exception:
                viewer._movie = None
                viewer._anim_is_playing = False
        else:
            viewer._anim_is_playing = False
    except Exception:
        try:
            viewer.image_display_area.set_animation_state(False)
        except Exception:
            pass
    try:
        viewer.log.info("apply_loaded | file=%s | source=%s | anim=%s", os.path.basename(path), source, bool(is_anim))
    except Exception:
        pass
    viewer.load_successful = True
    viewer.current_image_path = path
    viewer.update_window_title(path)
    if os.path.exists(path):
        viewer.scan_directory(os.path.dirname(path))
    viewer.update_button_states()
    viewer.update_status_left()
    viewer.update_status_right()
    viewer._tf_rotation = 0
    viewer._tf_flip_h = False
    viewer._tf_flip_v = False
    viewer._apply_transform_to_view()
    viewer._mark_dirty(False)
    try:
        viewer._history_undo.clear()
        viewer._history_redo.clear()
    except Exception:
        pass
    try:
        preload_neighbors(viewer)
    except Exception:
        pass
    if source in ('open', 'drop'):
        try:
            viewer.recent_files = update_mru(viewer.recent_files, path)
            parent_dir = os.path.dirname(path)
            if parent_dir and os.path.isdir(parent_dir):
                viewer.last_open_dir = parent_dir
            viewer.save_settings()
            viewer.rebuild_recent_menu()
        except Exception:
            pass
    try:
        # 즉시 스케일 적용 트리거 1회만 수행(중복 호출 제거)
        viewer._scale_apply_timer.start(0)
    except Exception:
        pass


def load_image(viewer: "JusawiViewer", file_path: str, source: str = 'other') -> bool:
    if viewer._is_dirty and viewer.current_image_path and os.path.normcase(file_path) != os.path.normcase(viewer.current_image_path):
        if not viewer._handle_dirty_before_action():
            try:
                viewer.log.info("load_image_aborted_dirty | new=%s | cur=%s", os.path.basename(file_path), os.path.basename(viewer.current_image_path or ""))
            except Exception:
                pass
            return False
    try:
        viewer.log.info("load_image_start | src=%s | source=%s", os.path.basename(file_path), source)
    except Exception:
        pass

    # 이전 애니메이션(QMovie) 정리: 프레임 시그널이 남아 이전 파일이 계속 그려지는 문제 방지
    try:
        if getattr(viewer, "_movie", None):
            try:
                try:
                    viewer._movie.frameChanged.disconnect(viewer._on_movie_frame)
                except Exception:
                    pass
                viewer._movie.stop()
            except Exception:
                pass
            try:
                viewer._movie.deleteLater()
            except Exception:
                pass
            viewer._movie = None
        try:
            if getattr(viewer, "_anim_timer", None):
                viewer._anim_timer.stop()
        except Exception:
            pass
        viewer._anim_is_playing = False
        try:
            viewer.image_display_area.set_animation_state(False)
        except Exception:
            pass
    except Exception:
        pass

    # 스케일 프리뷰 경로 비활성화: 항상 원본(또는 동등) 로드로 일관된 배율 보장

    # 폴백: 원본 동기 로드
    path, img, success, _ = viewer.image_service.load(file_path)
    if success and img is not None:
        apply_loaded_image(viewer, path, img, source)
        try:
            viewer.log.info("load_image_ok | file=%s | w=%d | h=%d", os.path.basename(path), int(img.width()), int(img.height()))
        except Exception:
            pass
        return True
    try:
        viewer.log.error("load_image_fail | file=%s", os.path.basename(file_path))
    except Exception:
        pass
    viewer.load_successful = False
    viewer.current_image_path = None
    viewer.image_files_in_dir = []
    viewer.current_image_index = -1
    viewer.update_window_title()
    viewer.update_button_states()
    viewer.update_status_left()
    viewer.update_status_right()
    return False


def preload_neighbors(viewer: "JusawiViewer") -> None:
    """현재 인덱스를 기준으로 다음/이전 이미지를 백그라운드로 프리로드."""
    if not viewer.image_files_in_dir:
        return
    idx = viewer.current_image_index
    if not (0 <= idx < len(viewer.image_files_in_dir)):
        return
    paths: list[str] = []
    for off in range(1, getattr(viewer, "_preload_radius", 2) + 1):
        n = idx + off
        p = idx - off
        if 0 <= n < len(viewer.image_files_in_dir):
            paths.append(viewer.image_files_in_dir[n])
        if 0 <= p < len(viewer.image_files_in_dir):
            paths.append(viewer.image_files_in_dir[p])
    if paths:
        try:
            viewer.image_service.preload(paths, priority=-1)
        except Exception:
            pass


