from .event_filters import DnDEventFilter


def enable_dnd(widget, event_filter_owner) -> None:
    try:
        widget.setAcceptDrops(True)
        # 개별 위젯에 동일한 필터 인스턴스를 설치해도 되나,
        # 여기서는 상위 소유자(viewer) 수준에 한 번 생성해 공유
        if not hasattr(event_filter_owner, "_dnd_event_filter"):
            event_filter_owner._dnd_event_filter = DnDEventFilter(event_filter_owner)
        widget.installEventFilter(event_filter_owner._dnd_event_filter)
    except Exception:
        pass


def setup_global_dnd(viewer) -> None:
    widgets = [
        viewer.centralWidget(),
        viewer.button_bar,
        viewer.open_button, viewer.recent_button, viewer.fullscreen_button, viewer.prev_button, viewer.next_button,
        viewer.zoom_out_button, viewer.fit_button, viewer.zoom_in_button,
        viewer.image_display_area,
        getattr(viewer.image_display_area, 'viewport', lambda: None)(),
        viewer.statusBar(), viewer.status_left_label, viewer.status_right_label,
    ]
    for w in widgets:
        if w:
            enable_dnd(w, viewer)


