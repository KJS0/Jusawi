from __future__ import annotations

import os
from typing import TYPE_CHECKING
from PyQt6.QtGui import QPixmap, QMovie  # type: ignore[import]

from ..storage.mru_store import update_mru

if TYPE_CHECKING:
    from .main_window import JusawiViewer


def apply_loaded_image(viewer: "JusawiViewer", path: str, img, source: str) -> None:
    # 확대 상태 유지 정책에 따라 변환/보기 초기화 수준 결정
    zoom_policy = str(getattr(viewer, "_zoom_policy", "mode"))
    # 요구사항: 변환 상태 유지하지 않음 → 항상 초기화(비파괴 표시만)
    try:
        viewer._tf_rotation = 0
        viewer._tf_flip_h = False
        viewer._tf_flip_v = False
    except Exception:
        pass
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
                    # 루프 설정 반영: True(무한 루프=0), False(1회 재생=1)
                    try:
                        mv.setLoopCount(0 if bool(getattr(viewer, "_anim_loop", True)) else 1)
                    except Exception:
                        pass
                    # 자동 재생 설정 반영
                    if bool(getattr(viewer, "_anim_autoplay", True)):
                        viewer._movie.start()
                        viewer._anim_is_playing = True
                    else:
                        # 정지 상태 유지
                        viewer._movie.stop()
                        viewer._anim_is_playing = False
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
        try:
            dirp = os.path.dirname(path)
            # 같은 폴더이고 목록에 이미 포함되어 있으면 재스캔 생략
            already_listed = False
            try:
                nc = os.path.normcase
                if viewer.image_files_in_dir:
                    listed_set = {nc(p) for p in viewer.image_files_in_dir}
                    already_listed = nc(path) in listed_set and nc(getattr(viewer, "_last_scanned_dir", "")) == nc(dirp)
            except Exception:
                already_listed = False
            # 열기/드롭으로 들어온 경우에는 설정에 따라 자동 스캔 여부 결정
            should_scan = True
            try:
                if source in ('open', 'drop') and not bool(getattr(viewer, "_open_scan_dir_after_open", True)):
                    should_scan = False
            except Exception:
                should_scan = True
            if should_scan and not already_listed:
                viewer.scan_directory(dirp)
        except Exception:
            try:
                if should_scan:
                    viewer.scan_directory(os.path.dirname(path))
            except Exception:
                pass
    viewer.update_button_states()
    viewer.update_status_left()
    viewer.update_status_right()
    # 변환 상태는 정책에 따라 유지/초기화되었으므로, 현재 뷰에 반영
    viewer._apply_transform_to_view()
    # 확대/보기 모드 적용: 정책에 따라 유지
    try:
        if zoom_policy == 'reset':
            pref = getattr(viewer, "_session_preferred_view_mode", None)
            if pref == 'fit':
                viewer.image_display_area.fit_to_window()
            elif pref == 'fit_width':
                viewer.image_display_area.fit_to_width()
            elif pref == 'fit_height':
                viewer.image_display_area.fit_to_height()
            elif pref == 'actual':
                viewer.image_display_area.reset_to_100()
        elif zoom_policy == 'mode':
            # 보기 모드 유지: 직전 모드를 반영
            pref = getattr(viewer, "_last_view_mode", 'fit')
            if pref == 'fit':
                viewer.image_display_area.fit_to_window()
            elif pref == 'fit_width':
                viewer.image_display_area.fit_to_width()
            elif pref == 'fit_height':
                viewer.image_display_area.fit_to_height()
            elif pref == 'actual':
                viewer.image_display_area.reset_to_100()
        elif zoom_policy == 'scale':
            # 배율 유지: 직전 스케일을 그대로 적용
            try:
                prev_scale = float(getattr(viewer, "_last_scale", 1.0))
            except Exception:
                prev_scale = 1.0
            if prev_scale and prev_scale > 0:
                viewer.image_display_area.set_absolute_scale(prev_scale)
        else:
            pass
    except Exception:
        pass
    # 보기 공유 옵션 제거됨
    viewer._mark_dirty(False)
    # 별점/플래그 표시 갱신(최초 로드시에도 즉시 반영)
    try:
        from . import rating_bar
        rating_bar.refresh(viewer)
    except Exception:
        pass
    # 필름 스트립 선택 동기화(내비게이션 등으로 변경 시 표시 반영)
    try:
        if hasattr(viewer, "filmstrip") and viewer.filmstrip is not None:
            if 0 <= viewer.current_image_index < len(viewer.image_files_in_dir):
                viewer.filmstrip.set_current_index(viewer.current_image_index)
    except Exception:
        pass
    # 필름스트립 인덱스 동기화 이후 한 번 더 갱신해 플래그 표시를 확실히 반영
    try:
        from . import rating_bar
        rating_bar.refresh(viewer)
    except Exception:
        pass
    # 정보 패널 갱신(보일 때만)
    try:
        if hasattr(viewer, "update_info_panel") and getattr(viewer, "info_text", None) is not None:
            if viewer.info_text.isVisible():
                viewer.update_info_panel()
    except Exception:
        pass
    try:
        viewer._history_undo.clear()
        viewer._history_redo.clear()
    except Exception:
        pass
    try:
        preload_neighbors(viewer)
    except Exception:
        pass
    # 자동화: AI 분석 자동 실행
    try:
        if bool(getattr(viewer, "_auto_ai_on_open", False)) and (source in ("open", "drop", "nav")):
            delay = max(0, int(getattr(viewer, "_auto_ai_delay_ms", 0)))
            from PyQt6.QtCore import QTimer  # type: ignore[import]
            def _run_ai():
                try:
                    viewer.open_ai_analysis_dialog()
                except Exception:
                    pass
            if delay > 0:
                QTimer.singleShot(delay, _run_ai)
            else:
                QTimer.singleShot(0, _run_ai)
    except Exception:
        pass
    if source in ('open', 'drop'):
        try:
            viewer.recent_files = update_mru(viewer.recent_files, path)
            parent_dir = os.path.dirname(path)
            if parent_dir and os.path.isdir(parent_dir):
                try:
                    if bool(getattr(viewer, "_remember_last_open_dir", True)):
                        viewer.last_open_dir = parent_dir
                except Exception:
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
    if not bool(getattr(viewer, "_enable_thumb_prefetch", True)):
        return
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


