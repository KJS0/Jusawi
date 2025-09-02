from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout  # type: ignore[import]
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize, QObject, QEvent  # type: ignore[import]


class _ToastWidget(QWidget):
    def __init__(self, message: str, kind: str = "info", duration_ms: int = 2000,
                 action_text: str | None = None, action_callback=None, parent: QWidget | None = None,
                 persistent: bool = False):
        super().__init__(parent)
        self._action_callback = action_callback
        self._persistent = bool(persistent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._label = QLabel(message, self)
        self._label.setWordWrap(True)
        self._button = None
        if action_text:
            btn = QPushButton(action_text, self)
            btn.clicked.connect(self._on_action)
            self._button = btn

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        layout.addWidget(self._label)
        if self._button is not None:
            layout.addWidget(self._button)

        # 색상 테마: 호스트의 시스템/사용자 테마를 반영
        host = parent
        resolved = None
        try:
            resolved = getattr(getattr(host, "parent", lambda: None)(), "_resolved_theme", None) if host else None
        except Exception:
            resolved = None
        if resolved is None and host is not None:
            try:
                resolved = getattr(host, "_resolved_theme", None)
            except Exception:
                resolved = None
        # 기본 다크
        base_bg = "#2f2f2f" if resolved != 'light' else "#FAFAFA"
        base_fg = "#EAEAEA" if resolved != 'light' else "#222222"
        # 종류별 강조색
        if kind == "success":
            bg = "#2e7d32" if resolved != 'light' else "#A5D6A7"
            fg = "#ffffff" if resolved != 'light' else "#1B5E20"
            border = "#1b5e20" if resolved != 'light' else "#81C784"
        elif kind == "error":
            bg = "#c62828" if resolved != 'light' else "#EF9A9A"
            fg = "#ffffff" if resolved != 'light' else "#B71C1C"
            border = "#8e0000" if resolved != 'light' else "#E57373"
        else:
            bg = base_bg
            fg = base_fg
            border = "#555555" if resolved != 'light' else "#DDDDDD"

        # 네모난 테두리, 시스템 테마 색, 살짝 반투명 음영 버튼
        self.setStyleSheet(
            f"background-color: {bg}; border: 1px solid {border}; border-radius: 4px;"
            f"QLabel {{ color: {fg}; }}"
            f"QPushButton {{ color: {fg}; background: transparent; border: 1px solid {border}; padding: 4px 8px; border-radius: 3px; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.12); }}"
        )

        self._timer = None
        if not self._persistent:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.close)
            self._timer.start(max(100, int(duration_ms)))

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        return QSize(max(240, base.width()), base.height())

    def _on_action(self):
        try:
            if callable(self._action_callback):
                self._action_callback()
        except Exception:
            pass
        self.close()


class ToastManager(QObject):
    def __init__(self, host: QWidget):
        super().__init__(host)
        self._host = host
        self._items: list[_ToastWidget] = []
        host.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self._host and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._relayout()
        return super().eventFilter(obj, event)

    def show_toast(self, message: str, kind: str = "info", duration_ms: int = 2000,
                   action_text: str | None = None, action_callback=None, persistent: bool = False) -> None:
        toast = _ToastWidget(message, kind, duration_ms, action_text, action_callback, parent=self._host, persistent=persistent)
        toast.setObjectName("toast")
        toast.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        toast.show()
        self._items.append(toast)
        toast.destroyed.connect(lambda *_: self._on_closed(toast))
        self._relayout()

    def _on_closed(self, toast: _ToastWidget):
        try:
            if toast in self._items:
                self._items.remove(toast)
        except Exception:
            pass
        self._relayout()

    def _relayout(self):
        if not self._items:
            return
        m = 16  # margin from window edge
        y = self._host.height() - m
        for toast in reversed(self._items):  # newest at bottom
            s = toast.sizeHint()
            y -= s.height()
            toast.resize(s)
            x = self._host.width() - s.width() - m
            toast.move(QPoint(max(m, x), max(m, y)))
            y -= 8  # gap


