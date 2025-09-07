from dataclasses import dataclass
from typing import List, Dict, Callable

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import Qt


@dataclass(frozen=True)
class Command:
    id: str
    label: str
    desc: str
    category: str
    handler_name: str
    default_keys: List[str]
    lock_key: bool = False  # true면 사용자 재매핑 불가(F1 등)


# 명령 레지스트리: 필요 시 추가/수정
COMMANDS: List[Command] = [
    Command("open_file", "파일 열기", "파일 열기 대화상자", "파일", "open_file", ["Ctrl+O"]),
    Command("toggle_fullscreen", "전체화면 토글", "전체화면 전환", "보기", "toggle_fullscreen", ["F11"]),
    Command("handle_escape", "나가기/전체화면 종료", "Esc 동작", "시스템", "handle_escape", ["Escape"], lock_key=True),
    Command("delete_current_image", "파일 삭제", "현재 파일을 휴지통으로", "파일", "delete_current_image", ["Delete"]),

    Command("show_prev_image", "이전 이미지", "이전 파일로 이동", "탐색", "show_prev_image", ["Left", "PageUp"]),
    # Space는 애니메이션 재생/일시정지용으로 사용하므로 기본 매핑에서 제외
    Command("show_next_image", "다음 이미지", "다음 파일로 이동", "탐색", "show_next_image", ["Right", "PageDown"]),
    Command("show_first_image", "첫 이미지", "첫 파일로 이동", "탐색", "show_first_image", ["Home"]),
    Command("show_last_image", "마지막 이미지", "마지막 파일로 이동", "탐색", "show_last_image", ["End"]),

    Command("fit_to_window", "화면 맞춤", "화면에 맞게 보기", "보기", "fit_to_window", ["F"]),
    Command("fit_to_width", "가로 맞춤", "너비에 맞게 보기", "보기", "fit_to_width", ["W"]),
    Command("fit_to_height", "세로 맞춤", "높이에 맞게 보기", "보기", "fit_to_height", ["H"]),
    Command("reset_to_100", "실제 크기(100%)", "배율 100%", "보기", "reset_to_100", ["1"]),
    # Ctrl+Plus/Ctrl+Equal 모두 허용(키보드 레이아웃에 따라 + 입력이 Shift+='가 될 수 있음)
    Command("zoom_in", "확대", "점진 확대", "보기", "zoom_in", ["Ctrl++", "Ctrl+="]),
    Command("zoom_out", "축소", "점진 축소", "보기", "zoom_out", ["Ctrl+-"]),

    # 회전은 기본 미할당(버튼만). 원하면 사용자가 매핑
    Command("rotate_ccw_90", "왼쪽 90° 회전", "반시계 방향 회전", "편집", "rotate_ccw_90", []),
    Command("rotate_cw_90", "오른쪽 90° 회전", "시계 방향 회전", "편집", "rotate_cw_90", []),
    Command("rotate_180", "180° 회전", "180도 회전", "편집", "rotate_180", ["2"]),
    Command("flip_horizontal", "좌우 뒤집기", "수평 반전", "편집", "flip_horizontal", ["Shift+H"]),
    Command("flip_vertical", "상하 뒤집기", "수직 반전", "편집", "flip_vertical", ["Shift+V"]),

    # 편집 히스토리
    Command("undo", "실행 취소", "마지막 편집 취소", "편집", "undo_action", ["Ctrl+Z"]),
    Command("redo", "다시 실행", "취소한 편집 다시 실행", "편집", "redo_action", ["Ctrl+Y", "Ctrl+Shift+Z"]),

    # 애니메이션 토글: Space 고정(다른 명령에 할당 금지)
    Command("toggle_animation", "애니메이션 토글", "재생/일시정지 전환", "보기", "anim_toggle_play", ["Space"], lock_key=True),

    # 도움말(F1)은 고정
    Command("help_shortcuts", "단축키 도움말", "현재 단축키 표시", "도움말", "open_shortcuts_help", ["F1"], lock_key=True),
]


def _load_custom_keymap(settings) -> Dict[str, List[str]]:
    keymap: Dict[str, List[str]] = {}
    try:
        for cmd in COMMANDS:
            raw = settings.value(f"keys/custom/{cmd.id}", "", str)
            if raw:
                parts = [p.strip() for p in raw.split(";") if p.strip()]
                if parts:
                    keymap[cmd.id] = parts
    except Exception:
        pass
    return keymap


def save_custom_keymap(settings, mapping: Dict[str, List[str]]) -> None:
    try:
        for cmd in COMMANDS:
            keys = mapping.get(cmd.id, [])
            # 고정 키는 저장하지 않음
            if cmd.lock_key:
                continue
            val = ";".join(keys)
            settings.setValue(f"keys/custom/{cmd.id}", val)
    except Exception:
        pass


def get_effective_keymap(settings) -> Dict[str, List[str]]:
    custom = _load_custom_keymap(settings)
    eff: Dict[str, List[str]] = {}
    for cmd in COMMANDS:
        if cmd.lock_key:
            eff[cmd.id] = cmd.default_keys[:]
            continue
        if cmd.id in custom and custom[cmd.id]:
            eff[cmd.id] = custom[cmd.id]
        else:
            eff[cmd.id] = cmd.default_keys[:]
    return eff


def apply_shortcuts(viewer) -> None:
    # 기존 단축키 제거
    try:
        for sc in getattr(viewer, "_shortcuts", []) or []:
            try:
                sc.setParent(None)
            except Exception:
                pass
    except Exception:
        pass
    viewer._shortcuts = []

    eff = get_effective_keymap(getattr(viewer, "settings", None))

    for cmd in COMMANDS:
        handler: Callable | None = getattr(viewer, cmd.handler_name, None)
        if not callable(handler):
            continue
        for key in eff.get(cmd.id, []) or []:
            # Space는 애니메이션 토글 전용으로 허용하고, 다른 명령에는 사용 금지
            if key and key.strip().lower() == "space" and cmd.id != "toggle_animation":
                continue
            try:
                sc = QShortcut(QKeySequence(key), viewer)
                if cmd.id == "toggle_animation":
                    try:
                        sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
                    except Exception:
                        pass
                sc.activated.connect(handler)
                viewer._shortcuts.append(sc)
            except Exception:
                # 키 파싱 실패 등은 무시
                pass


