from __future__ import annotations

from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt  # type: ignore[import]

if TYPE_CHECKING:
    from .main_window import JusawiViewer


def drag_enter(viewer: "JusawiViewer", event) -> None:
    if event.mimeData().hasUrls():
        event.acceptProposedAction()
    else:
        event.ignore()


def drag_move(viewer: "JusawiViewer", event) -> None:
    if event.mimeData().hasUrls():
        event.acceptProposedAction()
    else:
        event.ignore()


def drop(viewer: "JusawiViewer", event) -> None:
    urls = event.mimeData().urls()
    if not urls:
        event.ignore()
        return
    from ..dnd.dnd_handlers import urls_to_local_files
    import os
    paths = urls_to_local_files(urls)
    if not paths:
        event.ignore()
        return
    files = [p for p in paths if os.path.isfile(p)]
    if files:
        viewer._handle_dropped_files(files)
    event.acceptProposedAction()


def resize(viewer: "JusawiViewer", event) -> None:
    # QGraphicsView가 자체 맞춤을 처리하므로 특별 동작 없음
    # 필요 시 추후 앵커/뷰 모드에 따른 재적용을 여기서 수행
    return



def handle_key_press(viewer: "JusawiViewer", event) -> bool:
    try:
        if event.modifiers() == Qt.KeyboardModifier.NoModifier:
            k = event.key()
            # 일반 숫자 0..5 또는 텐키패드 0..5
            is_top_row = (Qt.Key.Key_0 <= k <= Qt.Key.Key_5)
            keypad_keys = (
                getattr(Qt.Key, 'Keypad0', None), getattr(Qt.Key, 'Keypad1', None), getattr(Qt.Key, 'Keypad2', None),
                getattr(Qt.Key, 'Keypad3', None), getattr(Qt.Key, 'Keypad4', None), getattr(Qt.Key, 'Keypad5', None)
            )
            is_keypad = k in {kk for kk in keypad_keys if kk is not None}
            if is_top_row or is_keypad:
                try:
                    key_to_num = {
                        Qt.Key.Key_0: 0, Qt.Key.Key_1: 1, Qt.Key.Key_2: 2, Qt.Key.Key_3: 3, Qt.Key.Key_4: 4, Qt.Key.Key_5: 5,
                    }
                    if getattr(Qt.Key, 'Keypad0', None) is not None:
                        key_to_num[getattr(Qt.Key, 'Keypad0')] = 0
                    if getattr(Qt.Key, 'Keypad1', None) is not None:
                        key_to_num[getattr(Qt.Key, 'Keypad1')] = 1
                    if getattr(Qt.Key, 'Keypad2', None) is not None:
                        key_to_num[getattr(Qt.Key, 'Keypad2')] = 2
                    if getattr(Qt.Key, 'Keypad3', None) is not None:
                        key_to_num[getattr(Qt.Key, 'Keypad3')] = 3
                    if getattr(Qt.Key, 'Keypad4', None) is not None:
                        key_to_num[getattr(Qt.Key, 'Keypad4')] = 4
                    if getattr(Qt.Key, 'Keypad5', None) is not None:
                        key_to_num[getattr(Qt.Key, 'Keypad5')] = 5
                    n = key_to_num.get(k, None)
                    if n is None and Qt.Key.Key_0 <= k <= Qt.Key.Key_5:
                        n = int(k) - int(Qt.Key.Key_0)
                except Exception:
                    n = None
                if n is not None:
                    viewer._on_set_rating(n)
                    return True
            # 플래그: Z, X, C
            if k == Qt.Key.Key_Z:
                viewer._on_set_flag('pick')
                return True
            if k == Qt.Key.Key_X:
                viewer._on_set_flag('rejected')
                return True
            if k == Qt.Key.Key_C:
                viewer._on_set_flag('unflagged')
                return True
    except Exception:
        pass
    return False

