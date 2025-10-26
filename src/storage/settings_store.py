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
        viewer._default_view_mode = "fit"
        viewer._remember_last_view_mode = True
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
        viewer.settings.setValue("edit/save_policy", getattr(viewer, "_save_policy", "discard"))
        viewer.settings.setValue("edit/jpeg_quality", int(getattr(viewer, "_jpeg_quality", 95)))
    except Exception:
        pass


