from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QDialogButtonBox, QCheckBox, QWidget
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")

        root = QVBoxLayout(self)

        # Theme
        theme_row = _LabeledRow("테마")
        self.theme_combo = QComboBox(self)
        # 표시는 한글, 내부 값은 별도 매핑 사용
        self.theme_combo.addItems(["시스템", "다크", "라이트"])
        self.theme_combo.setToolTip("앱 테마를 선택합니다. 시스템은 OS 테마를 따릅니다.")
        theme_row.set_widget(self.theme_combo)
        root.addLayout(theme_row)

        # Margins L,T,R,B
        margins_row = _LabeledRow("여백")
        margins_widget = QWidget(self)
        margins_layout = QHBoxLayout(margins_widget)
        margins_layout.setContentsMargins(0, 0, 0, 0)
        self.margin_left = _spin(0, 64, 5)
        self.margin_top = _spin(0, 64, 5)
        self.margin_right = _spin(0, 64, 5)
        self.margin_bottom = _spin(0, 64, 5)
        for w, tip in [
            (self.margin_left, "왼쪽 여백 (픽셀)"),
            (self.margin_top, "위쪽 여백 (픽셀)"),
            (self.margin_right, "오른쪽 여백 (픽셀)"),
            (self.margin_bottom, "아래 여백 (픽셀)"),
        ]:
            w.setToolTip(tip)
        for w in (self.margin_left, self.margin_top, self.margin_right, self.margin_bottom):
            margins_layout.addWidget(w)
        margins_row.set_widget(margins_widget)
        root.addLayout(margins_row)

        # Spacing
        spacing_row = _LabeledRow("간격")
        self.spacing_spin = _spin(0, 64, 6)
        self.spacing_spin.setToolTip("버튼/위젯 사이 간격 (픽셀)")
        spacing_row.set_widget(self.spacing_spin)
        root.addLayout(spacing_row)

        # Default view mode
        view_row = _LabeledRow("기본 보기 모드")
        self.view_combo = QComboBox(self)
        # 표시 한글, 내부 값은 매핑 사용
        self.view_combo.addItems(["화면 맞춤", "가로 맞춤", "세로 맞춤", "실제 크기"])
        self.view_combo.setToolTip("새 이미지/앱 시작 시 적용할 기본 보기 모드")
        view_row.set_widget(self.view_combo)
        root.addLayout(view_row)

        # Remember last view mode
        self.remember_check = QCheckBox("마지막 보기 모드 우선 사용", self)
        self.remember_check.setToolTip("체크 시 마지막으로 사용한 보기 모드를 우선 적용합니다.")
        root.addWidget(self.remember_check)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # populate from viewer
    def load_from_viewer(self, viewer):
        theme = getattr(viewer, "_theme", "dark")
        theme_map = {"system": "시스템", "dark": "다크", "light": "라이트"}
        idx = max(0, self.theme_combo.findText(theme_map.get(theme, "다크")))
        self.theme_combo.setCurrentIndex(idx)

        margins = getattr(viewer, "_ui_margins", (5, 5, 5, 5))
        try:
            self.margin_left.setValue(int(margins[0]))
            self.margin_top.setValue(int(margins[1]))
            self.margin_right.setValue(int(margins[2]))
            self.margin_bottom.setValue(int(margins[3]))
        except Exception:
            pass

        spacing = int(getattr(viewer, "_ui_spacing", 6))
        self.spacing_spin.setValue(spacing)

        dvm = getattr(viewer, "_default_view_mode", "fit")
        vm_map = {"fit": "화면 맞춤", "fit_width": "가로 맞춤", "fit_height": "세로 맞춤", "actual": "실제 크기"}
        idx_vm = max(0, self.view_combo.findText(vm_map.get(dvm, "화면 맞춤")))
        self.view_combo.setCurrentIndex(idx_vm)

        remember = bool(getattr(viewer, "_remember_last_view_mode", True))
        self.remember_check.setChecked(remember)

    # commit back to viewer (does not save)
    def apply_to_viewer(self, viewer):
        # 한글 → 내부 값 매핑
        theme_rev = {"시스템": "system", "다크": "dark", "라이트": "light"}
        viewer._theme = theme_rev.get(self.theme_combo.currentText(), "dark")
        viewer._ui_margins = (
            int(self.margin_left.value()),
            int(self.margin_top.value()),
            int(self.margin_right.value()),
            int(self.margin_bottom.value()),
        )
        viewer._ui_spacing = int(self.spacing_spin.value())
        vm_rev = {"화면 맞춤": "fit", "가로 맞춤": "fit_width", "세로 맞춤": "fit_height", "실제 크기": "actual"}
        viewer._default_view_mode = vm_rev.get(self.view_combo.currentText(), "fit")
        viewer._remember_last_view_mode = bool(self.remember_check.isChecked())


class _LabeledRow(QHBoxLayout):
    def __init__(self, label_text: str):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(label_text)
        self.addWidget(self._label)
        self._holder = QWidget()
        self._holder_layout = QHBoxLayout(self._holder)
        self._holder_layout.setContentsMargins(8, 0, 0, 0)
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


