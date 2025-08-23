import sys
import os
import pytest
from PyQt6.QtWidgets import QApplication

app = None

@pytest.fixture(scope="session", autouse=True)
def _app():
    global app
    if QApplication.instance() is None:
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app


def test_window_constructs(qtbot):
    from src.main_window import JusawiViewer

    w = JusawiViewer()
    qtbot.addWidget(w)
    assert w is not None
    assert hasattr(w, "recent_menu")


def test_recent_menu_clear_label(qtbot):
    from src.main_window import JusawiViewer

    w = JusawiViewer()
    qtbot.addWidget(w)
    actions = w.recent_menu.actions()
    assert actions, "recent menu should have at least one action"
    assert actions[-1].text() in ("지우기", "최근 목록 비우기") 