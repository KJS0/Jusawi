from __future__ import annotations

from typing import Protocol, Any

from PyQt6.QtWidgets import QWidget


class SettingsPage(QWidget):
    """설정 탭 공통 베이스.

    각 페이지는 아래 3가지 훅을 구현해 다이얼로그와 느슨하게 결합합니다.
      - load_from_viewer(viewer): 현재 뷰어 상태를 UI에 반영
      - apply_to_viewer(viewer): UI 값을 뷰어 필드에 반영(메모리만)
      - reset_to_defaults(): 페이지별 기본값으로 UI 리셋
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

    # 개별 페이지에서 필요 시 오버라이드
    def load_from_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        pass

    def apply_to_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        pass

    def reset_to_defaults(self) -> None:
        pass


