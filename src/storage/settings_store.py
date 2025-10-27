import os
from typing import Any, Dict

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # type: ignore


def _default_config_paths() -> list[str]:
    paths: list[str] = []
    # 1) 실행 디렉터리의 config.yaml
    try:
        exe_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        p = os.path.join(exe_dir, "config.yaml")
        paths.append(p)
    except Exception:
        pass
    # 2) 사용자 홈 디렉터리 하위
    try:
        home = os.path.expanduser("~")
        paths.append(os.path.join(home, ".jusawi", "config.yaml"))
        paths.append(os.path.join(home, "config.yaml"))
    except Exception:
        pass
    # 3) 환경변수로 지정된 경로 최우선
    env = os.getenv("JUSAWI_CONFIG")
    if env:
        paths.insert(0, env)
    # 중복 제거, 존재하는 파일만 유지(로드 단계에서 다시 체크)
    dedup: list[str] = []
    seen: set[str] = set()
    for p in paths:
        if not p:
            continue
        ap = os.path.abspath(os.path.expanduser(p))
        if ap not in seen:
            seen.add(ap)
            dedup.append(ap)
    return dedup


def _load_yaml_file(path: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    try:
        if not path or not os.path.isfile(path):
            return data
        if yaml is None:
            return data
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if isinstance(raw, dict):
            return raw  # type: ignore[return-value]
        return {}
    except Exception:
        return {}


def _merge_dict(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in (src or {}).items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _merge_dict(dst[k], v)  # type: ignore[index]
        else:
            dst[k] = v
    return dst


def _ensure_user_config_exists() -> str | None:
    # config.yaml 사용 중단: 항상 QSettings만 사용
    return None


def _load_yaml_configs() -> Dict[str, Any]:
    # YAML 설정은 사용하지 않음(롤백)
    return {}


def _apply_yaml_settings(viewer, cfg: Dict[str, Any]) -> None:
    # 구조 예시:
    # ui: { theme: dark|light|system, margins: [L,T,R,B], spacing: 6, default_view_mode, remember_last_view_mode }
    # edit: { save_policy: discard|overwrite|save_as, jpeg_quality: 95 }
    # keys: { custom: { cmd_id: ["Ctrl+O"] } }
    try:
        edit = cfg.get("edit", {}) if isinstance(cfg, dict) else {}
        if isinstance(edit, dict):
            pol = edit.get("save_policy")
            if isinstance(pol, str) and pol in ("discard", "overwrite", "save_as"):
                viewer._save_policy = pol
            q = edit.get("jpeg_quality")
            if isinstance(q, int):
                viewer._jpeg_quality = int(q)
        # 단축키 커스텀 키맵: QSettings에 반영하여 기존 경로 재사용
        keys = cfg.get("keys", {}) if isinstance(cfg, dict) else {}
        if isinstance(keys, dict):
            custom = keys.get("custom", {}) if isinstance(keys.get("custom"), dict) else {}
            try:
                from ..shortcuts.shortcuts_manager import save_custom_keymap
            except Exception:
                save_custom_keymap = None  # type: ignore
            if custom and save_custom_keymap and hasattr(viewer, "settings"):
                # 문자열 리스트만 허용, 잘못된 값은 무시
                valid_map: Dict[str, list[str]] = {}
                for cmd_id, arr in custom.items():
                    if isinstance(cmd_id, str) and isinstance(arr, (list, tuple)):
                        seqs = [str(x) for x in arr if isinstance(x, (str, int))]
                        valid_map[cmd_id] = seqs[:1]  # 단일 시퀀스 정책
                save_custom_keymap(viewer.settings, valid_map)
        # 고급 옵션
        adv = cfg.get("advanced", {}) if isinstance(cfg, dict) else {}
        if isinstance(adv, dict):
            if isinstance(adv.get("preload_radius"), int):
                viewer._preload_radius = int(adv.get("preload_radius"))
            if isinstance(adv.get("scale_apply_delay_ms"), int):
                viewer._scale_apply_delay_ms = int(adv.get("scale_apply_delay_ms"))
                try:
                    if hasattr(viewer, "_scale_apply_timer"):
                        viewer._scale_apply_timer.setInterval(int(viewer._scale_apply_delay_ms))
                except Exception:
                    pass
            if isinstance(adv.get("disable_scaled_cache_below_100"), bool):
                viewer._disable_scaled_cache_below_100 = bool(adv.get("disable_scaled_cache_below_100"))
            if isinstance(adv.get("preserve_visual_size_on_dpr_change"), bool):
                viewer._preserve_visual_size_on_dpr_change = bool(adv.get("preserve_visual_size_on_dpr_change"))
            if isinstance(adv.get("convert_movie_frames_to_srgb"), bool):
                viewer._convert_movie_frames_to_srgb = bool(adv.get("convert_movie_frames_to_srgb"))
            if isinstance(adv.get("image_cache_max_bytes"), int):
                viewer._img_cache_max_bytes = int(adv.get("image_cache_max_bytes"))
            if isinstance(adv.get("scaled_cache_max_bytes"), int):
                viewer._scaled_cache_max_bytes = int(adv.get("scaled_cache_max_bytes"))
    except Exception:
        pass


def load_settings(viewer) -> None:
    try:
        # QSettings 캐시 초기화: 잘못 저장된 고정/제거 키값 제거
        try:
            if hasattr(viewer, "settings"):
                # reset_to_100 강제 비움
                viewer.settings.remove("keys/custom/reset_to_100")
                # rotate_180에 숫자 '2'가 저장되어 있으면 제거
                try:
                    raw = str(viewer.settings.value("keys/custom/rotate_180", ""))
                    if raw and (raw.strip() == "2" or ";2" in raw or "2;" in raw):
                        # 숫자 키는 평점 용도로 예약, 회전에서 제거
                        viewer.settings.remove("keys/custom/rotate_180")
                except Exception:
                    pass
                # 구 기본 매핑 제거: Q,E,W,H,Shift+H,Shift+V, F(화면맞춤), Ctrl+-을 잘못 저장한 확대, Q를 잘못 저장한 축소, Shift+H를 잘못 저장한 180°
                for k in ("rotate_ccw_90", "rotate_cw_90", "fit_to_width", "fit_to_height", "flip_horizontal", "flip_vertical", "fit_to_window", "zoom_in", "zoom_out", "rotate_180"):
                    try:
                        raw = str(viewer.settings.value(f"keys/custom/{k}", ""))
                    except Exception:
                        raw = ""
                    if not raw:
                        continue
                    # 금지 키 제거
                    parts = [p.strip() for p in raw.split(";") if p.strip()]
                    filtered: list[str] = []
                    for p in parts:
                        # 공통 제거
                        if p in ("Q", "E", "W", "H", "Shift+H", "Shift+V"):
                            continue
                        # 화면 맞춤에 F 제거
                        if k == "fit_to_window" and p == "F":
                            continue
                        # 확대에 Ctrl+- 제거(오입력 방지)
                        if k == "zoom_in" and p == "Ctrl+-":
                            continue
                        # 축소에 Q 제거(오입력 방지)
                        if k == "zoom_out" and p == "Q":
                            continue
                        # 180도 회전에 Shift+H 제거(오입력 방지)
                        if k == "rotate_180" and p == "Shift+H":
                            continue
                        filtered.append(p)
                    parts = filtered
                    viewer.settings.setValue(f"keys/custom/{k}", ";".join(parts))
        except Exception:
            pass
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
        # UI 관련 QSettings 제거: 고정값으로 설정
        viewer._theme = "dark"
        viewer._ui_margins = (5, 5, 5, 5)
        viewer._ui_spacing = 6
        try:
            dvm = str(viewer.settings.value("ui/default_view_mode", "fit", str))
            if dvm not in ("fit", "fit_width", "fit_height", "actual"):
                dvm = "fit"
            viewer._default_view_mode = dvm
        except Exception:
            viewer._default_view_mode = "fit"
        viewer._remember_last_view_mode = True
        # Open/Animation/Dir/TIFF 옵션 기본값 로드
        try:
            viewer._open_scan_dir_after_open = bool(viewer.settings.value("open/scan_dir_after_open", True, bool))
        except Exception:
            viewer._open_scan_dir_after_open = True
        try:
            viewer._remember_last_open_dir = bool(viewer.settings.value("open/remember_last_dir", True, bool))
        except Exception:
            viewer._remember_last_open_dir = True
        # 최근/세션 옵션 로드
        try:
            viewer._startup_restore_policy = str(viewer.settings.value("session/startup_restore_policy", "always", str))
        except Exception:
            viewer._startup_restore_policy = "always"
        try:
            viewer._recent_max_items = int(viewer.settings.value("recent/max_items", 10))
        except Exception:
            viewer._recent_max_items = 10
        # 제외 규칙 삭제됨
        try:
            viewer._recent_auto_prune_missing = bool(viewer.settings.value("recent/auto_prune_missing", True, bool))
        except Exception:
            viewer._recent_auto_prune_missing = True
        try:
            viewer._anim_autoplay = bool(viewer.settings.value("anim/autoplay", True, bool))
        except Exception:
            viewer._anim_autoplay = True
        try:
            viewer._anim_loop = bool(viewer.settings.value("anim/loop", True, bool))
        except Exception:
            viewer._anim_loop = True
        try:
            viewer._dir_sort_mode = viewer.settings.value("dir/sort_mode", "metadata", str)
            if viewer._dir_sort_mode not in ("metadata", "name"):
                viewer._dir_sort_mode = "metadata"
        except Exception:
            viewer._dir_sort_mode = "metadata"
        try:
            viewer._dir_natural_sort = bool(viewer.settings.value("dir/natural_sort", True, bool))
        except Exception:
            viewer._dir_natural_sort = True
        try:
            viewer._dir_exclude_hidden_system = bool(viewer.settings.value("dir/exclude_hidden_system", True, bool))
        except Exception:
            viewer._dir_exclude_hidden_system = True
        try:
            viewer._tiff_open_first_page_only = bool(viewer.settings.value("tiff/open_first_page_only", True, bool))
        except Exception:
            viewer._tiff_open_first_page_only = True
        # Drag & Drop / 목록 정책
        try:
            viewer._drop_allow_folder = bool(viewer.settings.value("drop/allow_folder_drop", False, bool))
        except Exception:
            viewer._drop_allow_folder = False
        try:
            viewer._drop_use_parent_scan = bool(viewer.settings.value("drop/use_parent_scan", True, bool))
        except Exception:
            viewer._drop_use_parent_scan = True
        try:
            viewer._drop_show_overlay = bool(viewer.settings.value("drop/show_progress_overlay", True, bool))
        except Exception:
            viewer._drop_show_overlay = True
        try:
            viewer._drop_confirm_over_threshold = bool(viewer.settings.value("drop/confirm_over_threshold", True, bool))
        except Exception:
            viewer._drop_confirm_over_threshold = True
        try:
            viewer._drop_large_threshold = int(viewer.settings.value("drop/large_drop_threshold", 500))
        except Exception:
            viewer._drop_large_threshold = 500
        # Prefetch/성능
        try:
            viewer._enable_thumb_prefetch = bool(viewer.settings.value("prefetch/thumbs_enabled", True, bool))
        except Exception:
            viewer._enable_thumb_prefetch = True
        try:
            viewer._preload_radius = int(viewer.settings.value("prefetch/preload_radius", 2))
        except Exception:
            viewer._preload_radius = 2
        try:
            viewer._enable_map_prefetch = bool(viewer.settings.value("prefetch/map_enabled", True, bool))
        except Exception:
            viewer._enable_map_prefetch = True
        # 자동화
        try:
            viewer._auto_ai_on_open = bool(viewer.settings.value("ai/auto_on_open", False, bool))
        except Exception:
            viewer._auto_ai_on_open = False
        try:
            viewer._auto_ai_delay_ms = int(viewer.settings.value("ai/auto_delay_ms", 0))
        except Exception:
            viewer._auto_ai_delay_ms = 0
        # Navigation/Filmstrip/Zoom 정책 추가
        try:
            viewer._nav_wrap_ends = bool(viewer.settings.value("nav/wrap_ends", False, bool))
        except Exception:
            viewer._nav_wrap_ends = False
        try:
            viewer._nav_min_interval_ms = int(viewer.settings.value("nav/min_interval_ms", 100))
        except Exception:
            viewer._nav_min_interval_ms = 100
        try:
            viewer._filmstrip_auto_center = bool(viewer.settings.value("ui/filmstrip_auto_center", True, bool))
        except Exception:
            viewer._filmstrip_auto_center = True
        # 우선 정렬 키는 제거(메타데이터/파일명만 유지)
        try:
            viewer._zoom_policy = str(viewer.settings.value("view/zoom_policy", "mode", str))
            if viewer._zoom_policy not in ("reset", "mode", "scale"):
                viewer._zoom_policy = "mode"
        except Exception:
            viewer._zoom_policy = "mode"
        # 전체화면/오버레이 관련
        try:
            viewer._fs_auto_hide_ms = int(viewer.settings.value("fullscreen/auto_hide_ms", 1500))
        except Exception:
            viewer._fs_auto_hide_ms = 1500
        try:
            viewer._fs_auto_hide_cursor_ms = int(viewer.settings.value("fullscreen/auto_hide_cursor_ms", 1200))
        except Exception:
            viewer._fs_auto_hide_cursor_ms = 1200
        try:
            viewer._fs_enter_view_mode = str(viewer.settings.value("fullscreen/enter_view_mode", "keep", str))
            if viewer._fs_enter_view_mode not in ("keep", "fit", "fit_width", "fit_height", "actual"):
                viewer._fs_enter_view_mode = "keep"
        except Exception:
            viewer._fs_enter_view_mode = "keep"
        try:
            viewer._fs_show_filmstrip_overlay = bool(viewer.settings.value("fullscreen/show_filmstrip_overlay", False, bool))
        except Exception:
            viewer._fs_show_filmstrip_overlay = False
        try:
            viewer._fs_safe_exit = bool(viewer.settings.value("fullscreen/safe_exit_rule", True, bool))
        except Exception:
            viewer._fs_safe_exit = True
        try:
            viewer._overlay_enabled_default = bool(viewer.settings.value("overlay/enabled_default", False, bool))
        except Exception:
            viewer._overlay_enabled_default = False
        try:
            viewer._smooth_transform = bool(viewer.settings.value("view/smooth_transform", True, bool))
        except Exception:
            viewer._smooth_transform = True
        # 보기/줌 고급 옵션
        # 보기 공유 옵션 제거됨
        try:
            viewer._refit_on_transform = bool(viewer.settings.value("view/refit_on_transform", True, bool))
        except Exception:
            viewer._refit_on_transform = True
        # 회전 시 화면 중심 앵커 유지 옵션(기본 True)
        try:
            viewer._anchor_preserve_on_transform = bool(viewer.settings.value("view/anchor_preserve_on_transform", True, bool))
        except Exception:
            viewer._anchor_preserve_on_transform = True
        try:
            viewer._fit_margin_pct = int(viewer.settings.value("view/fit_margin_pct", 0))
        except Exception:
            viewer._fit_margin_pct = 0
        try:
            viewer._wheel_zoom_requires_ctrl = bool(viewer.settings.value("view/wheel_zoom_requires_ctrl", True, bool))
        except Exception:
            viewer._wheel_zoom_requires_ctrl = True
        try:
            viewer._wheel_zoom_alt_precise = bool(viewer.settings.value("view/wheel_zoom_alt_precise", True, bool))
        except Exception:
            viewer._wheel_zoom_alt_precise = True
        try:
            viewer._use_fixed_zoom_steps = bool(viewer.settings.value("view/use_fixed_zoom_steps", False, bool))
        except Exception:
            viewer._use_fixed_zoom_steps = False
        try:
            viewer._zoom_step_factor = float(viewer.settings.value("view/zoom_step_factor", 1.25))
        except Exception:
            viewer._zoom_step_factor = 1.25
        try:
            viewer._precise_zoom_step_factor = float(viewer.settings.value("view/precise_zoom_step_factor", 1.1))
        except Exception:
            viewer._precise_zoom_step_factor = 1.1
        try:
            viewer._double_click_action = str(viewer.settings.value("view/double_click_action", "toggle", str))
        except Exception:
            viewer._double_click_action = 'toggle'
        try:
            viewer._middle_click_action = str(viewer.settings.value("view/middle_click_action", "none", str))
        except Exception:
            viewer._middle_click_action = 'none'
        try:
            viewer._preserve_visual_size_on_dpr_change = bool(viewer.settings.value("view/preserve_visual_size_on_dpr_change", False, bool))
        except Exception:
            pass
        # YAML 구성 로드 제거(롤백)
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
        # 최근/세션 옵션 저장
        viewer.settings.setValue("session/startup_restore_policy", str(getattr(viewer, "_startup_restore_policy", "always")))
        viewer.settings.setValue("recent/max_items", int(getattr(viewer, "_recent_max_items", 10)))
        # 제외 규칙 저장 없음
        viewer.settings.setValue("recent/auto_prune_missing", bool(getattr(viewer, "_recent_auto_prune_missing", True)))
        viewer.settings.setValue("edit/save_policy", getattr(viewer, "_save_policy", "discard"))
        viewer.settings.setValue("edit/jpeg_quality", int(getattr(viewer, "_jpeg_quality", 95)))
        # Open/Animation/Dir/TIFF 옵션 저장
        viewer.settings.setValue("open/scan_dir_after_open", bool(getattr(viewer, "_open_scan_dir_after_open", True)))
        viewer.settings.setValue("open/remember_last_dir", bool(getattr(viewer, "_remember_last_open_dir", True)))
        viewer.settings.setValue("anim/autoplay", bool(getattr(viewer, "_anim_autoplay", True)))
        viewer.settings.setValue("anim/loop", bool(getattr(viewer, "_anim_loop", True)))
        viewer.settings.setValue("dir/sort_mode", str(getattr(viewer, "_dir_sort_mode", "metadata")))
        viewer.settings.setValue("dir/natural_sort", bool(getattr(viewer, "_dir_natural_sort", True)))
        viewer.settings.setValue("dir/exclude_hidden_system", bool(getattr(viewer, "_dir_exclude_hidden_system", True)))
        viewer.settings.setValue("tiff/open_first_page_only", bool(getattr(viewer, "_tiff_open_first_page_only", True)))
        # Navigation/Filmstrip/Zoom 정책 저장
        viewer.settings.setValue("nav/wrap_ends", bool(getattr(viewer, "_nav_wrap_ends", False)))
        viewer.settings.setValue("nav/min_interval_ms", int(getattr(viewer, "_nav_min_interval_ms", 100)))
        viewer.settings.setValue("ui/filmstrip_auto_center", bool(getattr(viewer, "_filmstrip_auto_center", True)))
        # dir/sort_primary 저장 제거
        viewer.settings.setValue("view/zoom_policy", str(getattr(viewer, "_zoom_policy", "mode")))
        # 전체화면/오버레이 관련 저장
        viewer.settings.setValue("fullscreen/auto_hide_ms", int(getattr(viewer, "_fs_auto_hide_ms", 1500)))
        viewer.settings.setValue("fullscreen/auto_hide_cursor_ms", int(getattr(viewer, "_fs_auto_hide_cursor_ms", 1200)))
        viewer.settings.setValue("fullscreen/enter_view_mode", str(getattr(viewer, "_fs_enter_view_mode", "keep")))
        viewer.settings.setValue("fullscreen/show_filmstrip_overlay", bool(getattr(viewer, "_fs_show_filmstrip_overlay", False)))
        viewer.settings.setValue("fullscreen/safe_exit_rule", bool(getattr(viewer, "_fs_safe_exit", True)))
        viewer.settings.setValue("overlay/enabled_default", bool(getattr(viewer, "_overlay_enabled_default", False)))
        # 기본 보기 모드 및 스무딩 저장
        viewer.settings.setValue("ui/default_view_mode", str(getattr(viewer, "_default_view_mode", "fit")))
        viewer.settings.setValue("view/smooth_transform", bool(getattr(viewer, "_smooth_transform", True)))
        # 보기/줌 고급 옵션 저장
        # 보기 공유 저장 제거
        viewer.settings.setValue("view/refit_on_transform", bool(getattr(viewer, "_refit_on_transform", True)))
        viewer.settings.setValue("view/anchor_preserve_on_transform", bool(getattr(viewer, "_anchor_preserve_on_transform", True)))
        viewer.settings.setValue("view/fit_margin_pct", int(getattr(viewer, "_fit_margin_pct", 0)))
        viewer.settings.setValue("view/wheel_zoom_requires_ctrl", bool(getattr(viewer, "_wheel_zoom_requires_ctrl", True)))
        viewer.settings.setValue("view/wheel_zoom_alt_precise", bool(getattr(viewer, "_wheel_zoom_alt_precise", True)))
        viewer.settings.setValue("view/use_fixed_zoom_steps", bool(getattr(viewer, "_use_fixed_zoom_steps", False)))
        viewer.settings.setValue("view/zoom_step_factor", float(getattr(viewer, "_zoom_step_factor", 1.25)))
        viewer.settings.setValue("view/precise_zoom_step_factor", float(getattr(viewer, "_precise_zoom_step_factor", 1.1)))
        viewer.settings.setValue("view/double_click_action", str(getattr(viewer, "_double_click_action", 'toggle')))
        viewer.settings.setValue("view/middle_click_action", str(getattr(viewer, "_middle_click_action", 'none')))
        viewer.settings.setValue("view/preserve_visual_size_on_dpr_change", bool(getattr(viewer, "_preserve_visual_size_on_dpr_change", False)))
        # Drag & Drop / 목록 정책 저장
        viewer.settings.setValue("drop/allow_folder_drop", bool(getattr(viewer, "_drop_allow_folder", False)))
        viewer.settings.setValue("drop/use_parent_scan", bool(getattr(viewer, "_drop_use_parent_scan", True)))
        viewer.settings.setValue("drop/show_progress_overlay", bool(getattr(viewer, "_drop_show_overlay", True)))
        viewer.settings.setValue("drop/confirm_over_threshold", bool(getattr(viewer, "_drop_confirm_over_threshold", True)))
        viewer.settings.setValue("drop/large_drop_threshold", int(getattr(viewer, "_drop_large_threshold", 500)))
        # Prefetch/성능 저장
        viewer.settings.setValue("prefetch/thumbs_enabled", bool(getattr(viewer, "_enable_thumb_prefetch", True)))
        viewer.settings.setValue("prefetch/preload_radius", int(getattr(viewer, "_preload_radius", 2)))
        viewer.settings.setValue("prefetch/map_enabled", bool(getattr(viewer, "_enable_map_prefetch", True)))
        # 자동화 저장
        viewer.settings.setValue("ai/auto_on_open", bool(getattr(viewer, "_auto_ai_on_open", False)))
        viewer.settings.setValue("ai/auto_delay_ms", int(getattr(viewer, "_auto_ai_delay_ms", 0)))
    except Exception:
        pass


