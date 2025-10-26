from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QDialogButtonBox, QCheckBox, QWidget, QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QApplication, QFormLayout, QFileDialog
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QKeySequenceEdit
from ..shortcuts.shortcuts_manager import COMMANDS, get_effective_keymap, save_custom_keymap


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self._reset_keys_to_defaults = False
        self._key_warning_active = False

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
        except Exception:
            pass
        self.tabs = QTabWidget(self)
        root.addWidget(self.tabs)


        # ----- 단축키 탭 -----
        self.keys_tab = QWidget(self)
        self.tabs.addTab(self.keys_tab, "단축키")
        self._keys_ready = False

        # 하단: 우측 확인/취소만 표시
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.addStretch(1)
        root.addLayout(bottom_row)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        # 탭 변경 시 크기 최적화
        try:
            self.tabs.currentChanged.connect(self._on_tab_changed)
        except Exception:
            pass
        # 초기 크기: 일반 탭에 맞춰 컴팩트하게
        try:
            self._on_tab_changed(0)
        except Exception:
            pass

    # 외부에서 호출: 단축키 탭으로 전환하고 첫 편집기로 포커스 이동
    def focus_shortcuts_tab(self):
        try:
            # 탭 전환
            idx = self.tabs.indexOf(self.keys_tab)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)
            # 필요 시 지연 초기화 실행
            if not getattr(self, "_keys_ready", False):
                self._build_keys_tab()
            # 첫 편집 가능한 필드로 포커스
            for ed in getattr(self, "_key_editors", []) or []:
                meta = getattr(self, "_editor_meta", {}).get(ed, {})
                if not meta.get("locked", False):
                    try:
                        ed.setFocus()
                        break
                    except Exception:
                        pass
        except Exception:
            pass

    # populate from viewer
    def load_from_viewer(self, viewer):
        # viewer 참조 저장(지연 로드시 사용)
        self._viewer_for_keys = viewer

    # commit back to viewer (does not save)
    def apply_to_viewer(self, viewer):
        # 키 저장(중복/금지 키 검증 포함)
        mapping = None
        if self._reset_keys_to_defaults:
            # 키 탭이 열려있지 않아도 기본값으로 저장
            mapping = {}
            for cmd in COMMANDS:
                if cmd.lock_key:
                    continue
                mapping[cmd.id] = cmd.default_keys[:1]
        elif getattr(self, "_keys_ready", False):
            mapping = self._collect_mapping_from_ui(validate_against_fixed=True)
            if mapping is None:
                return
        if mapping is not None:
            save_custom_keymap(getattr(viewer, "settings", None), mapping)
        self._reset_keys_to_defaults = False

    # ----- helpers -----
    def _on_reset_defaults(self):
        # 단축키 탭 기본값: 레지스트리의 default_keys로 되돌림(없으면 비움)
        # 테이블은 COMMANDS 순으로 채워져 있음
        if getattr(self, "_keys_ready", False) and hasattr(self, "keys_table"):
            row = 0
            for cmd in COMMANDS:
                editor = self.keys_table.cellWidget(row, 3) if row < self.keys_table.rowCount() else None
                if isinstance(editor, QKeySequenceEdit):
                    defaults = cmd.default_keys[:]
                    editor.setKeySequence(QKeySequence(defaults[0]) if defaults else QKeySequence())
                row += 1
        self._reset_keys_to_defaults = True

    def _on_accept(self):
        # 적용 전에 유효성 검사 수행 후 통과하면 accept
        # viewer에 직접 접근하지 않고 저장할 매핑만 검증
        if not self._reset_keys_to_defaults and not getattr(self, "_keys_ready", False):
            # 키 탭이 초기화되지 않았다면 단축키 검증은 건너뜀
            self.accept()
            return
        mapping = self._collect_mapping_from_ui(validate_against_fixed=True)
        if mapping is None:
            return
        self.accept()

    def _on_import_yaml(self):
        # 제거됨
        return

    def _on_export_yaml(self):
        # 제거됨
        return

    def _on_tab_changed(self, index: int):
        # 일반 탭은 작게, 단축키 탭은 내용 기반으로 크게
        try:
            tab_text = self.tabs.tabText(index)
        except Exception:
            tab_text = ""
        if tab_text == "단축키":
            # 지연 초기화
            if not getattr(self, "_keys_ready", False):
                try:
                    self._build_keys_tab()
                except Exception:
                    pass
            try:
                # 단축키 탭 크기 재조정
                header = self.keys_table.horizontalHeader()
                header.resizeSections(QHeaderView.ResizeMode.ResizeToContents)
            except Exception:
                pass
            # 기본 넉넉한 크기
            self.resize(max(860, self.width()), max(520, self.height()))
        else:
            # 일반 탭: 컴팩트 크기 강제
            self.resize(520, 360)

    def _build_keys_tab(self):
        # 실제 키 탭 UI 구성 및 데이터 로드
        keys_layout = QVBoxLayout(self.keys_tab)
        self.keys_table = QTableWidget(0, 4, self.keys_tab)
        self.keys_table.setHorizontalHeaderLabels(["조건", "명령", "설명", "단축키"])
        try:
            # 표 셀 선택/편집 비활성화(편집기는 별도 위젯으로 사용)
            from PyQt6.QtWidgets import QAbstractItemView
            self.keys_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.keys_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        except Exception:
            pass
        keys_layout.addWidget(self.keys_table)
        self._keys_ready = True
        # 데이터 채우기
        viewer = getattr(self, "_viewer_for_keys", None)
        eff = get_effective_keymap(getattr(viewer, "settings", None))
        self.keys_table.setRowCount(0)
        self._key_editors = []
        self._editor_meta = {}
        for cmd in [c for c in COMMANDS if c.id != "reset_to_100"]:
            row = self.keys_table.rowCount()
            self.keys_table.insertRow(row)
            cond_text = "고정" if cmd.lock_key else "-"
            it0 = QTableWidgetItem(cond_text)
            it1 = QTableWidgetItem(cmd.label)
            it2 = QTableWidgetItem(cmd.desc)
            # 입력/선택 불가, 표시만
            try:
                it0.setFlags(Qt.ItemFlag.ItemIsEnabled)
                it1.setFlags(Qt.ItemFlag.ItemIsEnabled)
                it2.setFlags(Qt.ItemFlag.ItemIsEnabled)
            except Exception:
                pass
            self.keys_table.setItem(row, 0, it0)
            self.keys_table.setItem(row, 1, it1)
            self.keys_table.setItem(row, 2, it2)
            # 읽기 전용 텍스트로 표시(여러 키가 있을 경우 ; 로 연결)
            seqs = eff.get(cmd.id, []) or []
            txt = "; ".join([str(s) for s in seqs]) if seqs else ""
            it3 = QTableWidgetItem(txt)
            try:
                it3.setFlags(Qt.ItemFlag.ItemIsEnabled)
            except Exception:
                pass
            self.keys_table.setItem(row, 3, it3)
        # 컬럼/크기 조정
        try:
            header = self.keys_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            self.keys_table.resizeColumnsToContents()
        except Exception:
            pass

    def _collect_mapping_from_ui(self, validate_against_fixed: bool = True):
        from PyQt6.QtWidgets import QMessageBox
        # 열람 전용: 현재 테이블의 텍스트를 그대로 저장 대상으로 수집
        mapping: dict[str, list[str]] = {}
        if getattr(self, "_keys_ready", False) and hasattr(self, "keys_table"):
            for row in range(self.keys_table.rowCount()):
                cmd = COMMANDS[row]
                item = self.keys_table.item(row, 3)
                txt = item.text().strip() if item else ""
                mapping[cmd.id] = [txt] if txt else []

        # 유효성 검사: 중복, 고정키 충돌, 예약키 금지
        if validate_against_fixed:
            used: dict[str, str] = {}
            # 고정키(F1, Escape 등) 집합
            fixed_keys = set()
            for cmd in COMMANDS:
                if cmd.lock_key:
                    for k in cmd.default_keys:
                        if k:
                            fixed_keys.add(k)
            # 예약키(확장 가능)
            reserved = {"Alt+F4"}

            # 중복 및 금지 검사
            for cmd in COMMANDS:
                if cmd.lock_key:
                    continue
                keys = mapping.get(cmd.id, []) or []
                if not keys:
                    continue
                k = keys[0]
                if k in reserved:
                    QMessageBox.warning(self, "단축키 오류", f"예약된 단축키 '{k}' 는 사용할 수 없습니다.")
                    return None
                if k in fixed_keys:
                    # 고정키와 충돌
                    QMessageBox.warning(self, "단축키 충돌", f"'{k}' 는 시스템/고정 단축키와 충돌합니다.")
                    return None
                if k in used:
                    # 다른 명령과 중복
                    other = used[k]
                    QMessageBox.warning(self, "단축키 중복", f"'{k}' 가 '{other}' 와(과) 중복됩니다. 다른 키를 지정하세요.")
                    return None
                used[k] = cmd.label

        return mapping

    def _normalize_single_key(self, editor: QKeySequenceEdit):
        try:
            seq = editor.keySequence()
            if not seq or seq.isEmpty():
                return
            # 표준 텍스트로 변환
            try:
                from PyQt6.QtGui import QKeySequence as _QS
                text = seq.toString(_QS.SequenceFormat.PortableText)
            except Exception:
                text = seq.toString()
            # 여러 파트가 "," 로 구분되어 들어올 수 있으므로 마지막 파트만 유지
            parts = [p.strip() for p in text.split(',') if p.strip()]
            last_part = parts[-1] if parts else ''
            # 수정키만 있는 조합 문자열 집합(PortableText 기준)
            mod_only = {
                "Ctrl", "Shift", "Alt", "Meta",
                "Ctrl+Shift", "Ctrl+Alt", "Ctrl+Meta",
                "Shift+Alt", "Shift+Meta", "Alt+Meta",
                "Ctrl+Shift+Alt", "Ctrl+Shift+Meta", "Ctrl+Alt+Meta",
                "Shift+Alt+Meta", "Ctrl+Shift+Alt+Meta"
            }
            if last_part in mod_only:
                editor.blockSignals(True)
                editor.setKeySequence(QKeySequence())
                editor.blockSignals(False)
                return
            # 최종 1개 시퀀스로 고정
            editor.blockSignals(True)
            editor.setKeySequence(QKeySequence(last_part))
            editor.blockSignals(False)
        except Exception:
            pass

    def _on_key_changed(self, editor: QKeySequenceEdit, defaults: list, row_idx: int):
        # 정규화 수행
        self._normalize_single_key(editor)
        # 중복/금지/고정 충돌 즉시 검사
        try:
            cur_txt = self._seq_to_text(editor.keySequence())
            def_txt = self._normalize_default_text(defaults)
            # 빈 값이면 버튼만 동기화하고 끝
            if not cur_txt:
                btn = self.keys_table.cellWidget(row_idx, 4)
                if isinstance(btn, QPushButton):
                    btn.setEnabled(False)
                return
            # 고정키/예약키 집합
            fixed_keys = set()
            for cmd in COMMANDS:
                if cmd.lock_key:
                    for k in cmd.default_keys:
                        if k:
                            fixed_keys.add(k)
            reserved = {"Alt+F4"}
            # 현재 행 외 사용중 키 수집
            used = set()
            for r in range(self.keys_table.rowCount()):
                if r == row_idx:
                    continue
                item = self.keys_table.item(r, 3)
                k = item.text().strip() if item else ""
                if k:
                    used.add(k)
            if cur_txt in reserved:
                self._show_key_warning("단축키 오류", f"예약된 단축키 '{cur_txt}' 는 사용할 수 없습니다.", editor)
                meta = getattr(self, "_editor_meta", {}).get(editor, {})
                prev_txt = meta.get("prev", "") if isinstance(meta, dict) else ""
                editor.blockSignals(True)
                editor.setKeySequence(QKeySequence(prev_txt) if prev_txt else QKeySequence())
                editor.blockSignals(False)
                cur_txt = prev_txt
            elif cur_txt in fixed_keys:
                self._show_key_warning("단축키 충돌", f"'{cur_txt}' 는 시스템/고정 단축키와 충돌합니다.", editor)
                meta = getattr(self, "_editor_meta", {}).get(editor, {})
                prev_txt = meta.get("prev", "") if isinstance(meta, dict) else ""
                editor.blockSignals(True)
                editor.setKeySequence(QKeySequence(prev_txt) if prev_txt else QKeySequence())
                editor.blockSignals(False)
                cur_txt = prev_txt
            elif cur_txt in used:
                self._show_key_warning("단축키 중복", f"'{cur_txt}' 가 이미 다른 명령에 할당되어 있습니다.", editor)
                meta = getattr(self, "_editor_meta", {}).get(editor, {})
                prev_txt = meta.get("prev", "") if isinstance(meta, dict) else ""
                editor.blockSignals(True)
                editor.setKeySequence(QKeySequence(prev_txt) if prev_txt else QKeySequence())
                editor.blockSignals(False)
                cur_txt = prev_txt
            # 기본값 버튼 상태 업데이트
            btn = self.keys_table.cellWidget(row_idx, 4)
            if isinstance(btn, QPushButton):
                btn.setEnabled(bool(def_txt) and cur_txt != def_txt)
        except Exception:
            pass

    def _show_key_warning(self, title: str, text: str, editor: QKeySequenceEdit | None):
        # 동일 시점 중복 팝업 방지 및 포커스 이동 보장
        try:
            if self._key_warning_active:
                return
            self._key_warning_active = True
            from PyQt6.QtWidgets import QMessageBox
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(title)
            box.setText(text)
            box.setWindowModality(Qt.WindowModality.ApplicationModal)
            try:
                box.raise_()
                box.activateWindow()
            except Exception:
                pass
            box.exec()
        except Exception:
            pass
        finally:
            self._key_warning_active = False
            try:
                if editor is not None:
                    editor.setFocus()
            except Exception:
                pass

    def _seq_to_text(self, seq: QKeySequence) -> str:
        try:
            from PyQt6.QtGui import QKeySequence as _QS
            return seq.toString(_QS.SequenceFormat.PortableText) if seq and not seq.isEmpty() else ""
        except Exception:
            return seq.toString() if seq and not seq.isEmpty() else ""

    def _normalize_default_text(self, defaults: list) -> str:
        if not defaults:
            return ""
        return str(defaults[0])

    # 이벤트 필터: 배타 포커스 + Backspace/Delete로 해제 지원
    def eventFilter(self, obj, event):
        try:
            if isinstance(obj, QKeySequenceEdit):
                if event.type() == QEvent.Type.FocusIn:
                    # 다른 에디터 포커스 제거
                    for ed in getattr(self, "_key_editors", []) or []:
                        if ed is not obj and ed.hasFocus():
                            try:
                                ed.clearFocus()
                            except Exception:
                                pass
                elif event.type() == QEvent.Type.KeyPress:
                    key = getattr(event, 'key', None)
                    # Backspace/Delete 처리: 키 해제
                    if key and int(key()) in (0x01000003, 0x01000007):  # Qt.Key_Backspace, Qt.Key_Delete
                        obj.setKeySequence(QKeySequence())
                        meta = getattr(self, "_editor_meta", {}).get(obj, None)
                        if meta is not None:
                            self._on_key_changed(obj, meta.get("defaults", []), int(meta.get("row", 0)))
                        return True
        except Exception:
            pass
        return super().eventFilter(obj, event)


class _LabeledRow(QHBoxLayout):
    def __init__(self, label_text: str):
        super().__init__()
        try:
            self.setContentsMargins(0, 0, 0, 0)
            self.setSpacing(0)
        except Exception:
            pass
        self._label = QLabel(label_text)
        try:
            self._label.setMinimumWidth(0)
            self._label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        except Exception:
            pass
        self.addWidget(self._label)
        self._holder = QWidget()
        self._holder_layout = QHBoxLayout(self._holder)
        try:
            self._holder_layout.setContentsMargins(0, 0, 0, 0)
            self._holder_layout.setSpacing(0)
        except Exception:
            pass
        self.addWidget(self._holder, 1)

    def set_widget(self, w: QWidget):
        # clear holder
        while self._holder_layout.count():
            item = self._holder_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._holder_layout.addWidget(w)


def _spin(min_v: int, max_v: int, value: int) -> QSpinBox:
    s = QSpinBox()
    s.setRange(min_v, max_v)
    s.setValue(value)
    return s


