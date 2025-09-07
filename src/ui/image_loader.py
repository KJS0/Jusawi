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

    # 스케일 우선 경로: 애니메이션 제외, 뷰 모드가 맞춤 계열일 때 뷰포트 기준 스케일 디코딩 시도
    try:
        view_mode = str(getattr(viewer.image_display_area, "_view_mode", "free") or "free")
    except Exception:
        view_mode = "free"
    try:
        is_anim, _fc = viewer.image_service.probe_animation(file_path)
    except Exception:
        is_anim = False
    if not is_anim and view_mode in ("fit", "fit_width", "fit_height"):
        try:
            vp = viewer.image_display_area.viewport().rect()
            vw = int(max(1, vp.width()))
            vh = int(max(1, vp.height()))
        except Exception:
            vw, vh = 0, 0
        try:
            dpr = float(viewer.image_display_area.viewport().devicePixelRatioF())
        except Exception:
            try:
                dpr = float(viewer.devicePixelRatioF())
            except Exception:
                dpr = 1.0
        scaled = None
        if vw > 0 and vh > 0:
            try:
                # 약간의 헤드룸으로 미세 줌 인 시 재디코드 빈도 감소
                scaled = viewer.image_service.get_scaled_for_viewport(file_path, vw, vh, view_mode=view_mode, dpr=dpr, headroom=1.1)
            except Exception:
                scaled = None
        if scaled is not None and not scaled.isNull():
            # 프리뷰 적용(원본은 아직 로드하지 않음)
            pixmap = QPixmap.fromImage(scaled)
            viewer.image_display_area.setPixmap(pixmap)
            # 자연 해상도는 EXIF 변환 반영된 원본 크기 기준으로 설정
            try:
                from PyQt6.QtGui import QImageReader  # type: ignore[import]
                r = QImageReader(file_path)
                r.setAutoTransform(True)
                osize = r.size()
                if osize.isValid():
                    viewer.image_display_area._natural_width = int(osize.width())
                    viewer.image_display_area._natural_height = int(osize.height())
                else:
                    viewer.image_display_area._natural_width = int(pixmap.width())
                    viewer.image_display_area._natural_height = int(pixmap.height())
            except Exception:
                pass
            try:
                viewer._fullres_image = None
            except Exception:
                viewer._fullres_image = None
            # 상태 갱신 및 부수효과(애니메이션 경로는 위에서 제외)
            viewer.load_successful = True
            viewer.current_image_path = file_path
            viewer.update_window_title(file_path)
            if os.path.exists(file_path):
                viewer.scan_directory(os.path.dirname(file_path))
            viewer.update_button_states()
            viewer.update_status_left()
            viewer.update_status_right()
            viewer._tf_rotation = 0
            viewer._tf_flip_h = False
            viewer._tf_flip_v = False
            viewer._apply_transform_to_view()
            # 소스 스케일을 실제 다운샘플 비율로 설정해 좌표계를 원본 기준으로 매핑
            try:
                nat_w = int(getattr(viewer.image_display_area, "_natural_width", 0) or 0)
                nat_h = int(getattr(viewer.image_display_area, "_natural_height", 0) or 0)
                pix_w = int(pixmap.width())
                pix_h = int(pixmap.height())
                try:
                    dpr = float(viewer.image_display_area.viewport().devicePixelRatioF())
                except Exception:
                    dpr = 1.0
                if nat_w > 0 and nat_h > 0 and pix_w > 0 and pix_h > 0:
                    s_w = (pix_w / float(nat_w)) / float(dpr)
                    s_h = (pix_h / float(nat_h)) / float(dpr)
                    src_scale = max(0.01, min(1.0, min(s_w, s_h)))
                else:
                    src_scale = 1.0
                viewer.image_display_area.set_source_scale(src_scale)
            except Exception:
                pass
            # 좌표/상태 즉시 갱신
            try:
                from PyQt6.QtCore import QPointF  # type: ignore[import]
                vp_center = viewer.image_display_area.viewport().rect().center()
                viewer.image_display_area._emit_cursor_pos_at_viewport_point(QPointF(vp_center))
                viewer.update_status_right()
                viewer.update_status_left()
            except Exception:
                pass
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
                    viewer.recent_files = update_mru(viewer.recent_files, file_path)
                    parent_dir = os.path.dirname(file_path)
                    if parent_dir and os.path.isdir(parent_dir):
                        viewer.last_open_dir = parent_dir
                    viewer.save_settings()
                    viewer.rebuild_recent_menu()
                except Exception:
                    pass
            try:
                # 즉시 스케일 적용 및 업그레이드 예약
                viewer._scale_apply_timer.start(0)
            except Exception:
                pass
            try:
                viewer._is_scaled_preview = True
                if viewer._fullres_upgrade_timer.isActive():
                    viewer._fullres_upgrade_timer.stop()
                # 빠르게 넘길 때는 약간의 텀을 주어 디코드 폭주 방지
                viewer._fullres_upgrade_timer.start(100)
            except Exception:
                pass
            # 짧은 텀 뒤 업그레이드 시도(이중 보장)
            try:
                from PyQt6.QtCore import QTimer  # type: ignore[import]
                QTimer.singleShot(100, getattr(viewer, "_upgrade_to_fullres_if_needed", lambda: None))
            except Exception:
                pass
            try:
                viewer.log.info("load_image_ok_scaled | file=%s | w=%d | h=%d", os.path.basename(file_path), int(scaled.width()), int(scaled.height()))
            except Exception:
                pass
            return True

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


