from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QHBoxLayout,
)

from ...shortcuts.shortcuts_manager import COMMANDS, get_effective_keymap, save_custom_keymap
from .base import SettingsPage


class KeysSettingsPage(SettingsPage):
    """단축키 탭: 현재 키맵 표시 + 기본값 복원만 지원.

    편집 UI는 별도 다이얼로그로 유지하고, 여기서는 읽기 전용과 기본값 복원 흐름만 제공한다.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reset_to_defaults = False

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(6)
        except Exception:
            pass

        # 표
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["조건", "명령", "설명", "단축키"])
        try:
            header = self.table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        except Exception:
            pass
        root.addWidget(self.table)

        # 하단 버튼: 기본값 복원
        row = QHBoxLayout()
        self.btn_reset = QPushButton("단축키 기본값으로 복원", self)
        try:
            self.btn_reset.clicked.connect(self._on_reset)
        except Exception:
            pass
        row.addWidget(self.btn_reset)
        row.addStretch(1)
        root.addLayout(row)

    def _on_reset(self) -> None:
        self._reset_to_defaults = True

    def load_from_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        eff = get_effective_keymap(getattr(viewer, "settings", None))
        self.table.setRowCount(0)
        for cmd in [c for c in COMMANDS if c.id != "reset_to_100"]:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cond_text = "고정" if cmd.lock_key else "-"
            it0 = QTableWidgetItem(cond_text)
            it1 = QTableWidgetItem(cmd.label)
            it2 = QTableWidgetItem(cmd.desc)
            for it in (it0, it1, it2):
                try:
                    it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                except Exception:
                    pass
            self.table.setItem(row, 0, it0)
            self.table.setItem(row, 1, it1)
            self.table.setItem(row, 2, it2)
            seqs = eff.get(cmd.id, []) or []
            txt = "; ".join([str(s) for s in seqs]) if seqs else ""
            it3 = QTableWidgetItem(txt)
            try:
                it3.setFlags(Qt.ItemFlag.ItemIsEnabled)
            except Exception:
                pass
            self.table.setItem(row, 3, it3)

    def apply_to_viewer(self, viewer: Any) -> None:  # noqa: ANN401
        if not self._reset_to_defaults:
            return
        mapping: dict[str, list[str]] = {}
        for cmd in COMMANDS:
            if cmd.lock_key:
                continue
            mapping[cmd.id] = cmd.default_keys[:1]
        try:
            save_custom_keymap(getattr(viewer, "settings", None), mapping)
        except Exception:
            pass
        self._reset_to_defaults = False

    def reset_to_defaults(self) -> None:
        self._reset_to_defaults = True


