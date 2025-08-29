from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QApplication
from PyQt6.QtCore import Qt
from .shortcuts_manager import COMMANDS, get_effective_keymap


class ShortcutsHelpDialog(QDialog):
    def __init__(self, viewer):
        super().__init__(viewer)
        self.setWindowTitle("단축키 목록")
        self._viewer = viewer
        try:
            self.setSizeGripEnabled(True)
        except Exception:
            pass

        root = QVBoxLayout(self)

        # 검색
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("명령/설명/단축키 검색…")
        self.search_edit.textChanged.connect(self._apply_filter)
        search_row.addWidget(self.search_edit)
        root.addLayout(search_row)

        # 테이블
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["명령", "설명", "단축키"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.table)

        # 닫기 버튼
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton("닫기", self)
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        self._all_rows = []  # (label, desc, keys_text)
        self._populate()
        self._adjust_size_to_content()

    def _populate(self):
        eff = get_effective_keymap(getattr(self._viewer, "settings", None))
        self._all_rows.clear()
        for cmd in COMMANDS:
            keys = eff.get(cmd.id, []) or []
            keys_text = "; ".join(keys) if keys else "-"
            self._all_rows.append((cmd.label, cmd.desc, keys_text))
        self._refresh_table(self._all_rows)

    def _apply_filter(self, text: str):
        q = (text or "").strip().lower()
        if not q:
            self._refresh_table(self._all_rows)
            return
        filtered = []
        for row in self._all_rows:
            if any(q in (cell or "").lower() for cell in row):
                filtered.append(row)
        self._refresh_table(filtered)

    def _refresh_table(self, rows):
        self.table.setRowCount(0)
        for (label, desc, keys_text) in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(label))
            self.table.setItem(r, 1, QTableWidgetItem(desc))
            self.table.setItem(r, 2, QTableWidgetItem(keys_text))
        self._adjust_size_to_content()

    def _adjust_size_to_content(self):
        try:
            header = self.table.horizontalHeader()
            # 콘텐츠 기준으로 폭 계산. 마지막 컬럼은 유연하게
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            self.table.resizeColumnsToContents()
            # 화면 크기 기준으로 다이얼로그 크기 결정
            screen = QApplication.primaryScreen()
            avail = screen.availableGeometry() if screen else None
            max_w = int(avail.width() * 0.8) if avail else 1000
            max_h = int(avail.height() * 0.8) if avail else 700
            # 내용에 따른 최소 크기 추정
            col_w = 0
            for i in range(self.table.columnCount()):
                col_w += header.sectionSize(i)
            # 여유 여백(스크롤바/패딩)
            col_w += 48
            # 높이 계산(행 수 제한하여 과도 확장 방지)
            rows = self.table.rowCount()
            row_h = self.table.verticalHeader().defaultSectionSize()
            header_h = self.table.horizontalHeader().height()
            est_h = header_h + min(rows, 20) * row_h + 96
            w = min(col_w, max_w)
            h = min(est_h, max_h)
            # 너무 작지 않게 기본값 보정
            w = max(w, 640)
            h = max(h, 360)
            self.resize(w, h)
        except Exception:
            try:
                self.resize(720, 420)
            except Exception:
                pass


