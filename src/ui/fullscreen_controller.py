from PyQt6.QtCore import Qt, QTimer


def enter_fullscreen(viewer):
    # 현재 창 상태 저장
    viewer.previous_window_state = {
        'geometry': viewer.geometry(),
        'window_state': viewer.windowState(),
        'maximized': viewer.isMaximized()
    }

    viewer.is_fullscreen = True

    # 버튼 바 컨테이너 숨김
    if hasattr(viewer, 'button_bar') and viewer.button_bar:
        viewer.button_bar.hide()

    # 상태바 숨김
    viewer.statusBar().hide()

    # 레이아웃 마진 제거
    margins = viewer.main_layout.contentsMargins()
    viewer._normal_margins = (margins.left(), margins.top(), margins.right(), margins.bottom())
    viewer.main_layout.setContentsMargins(0, 0, 0, 0)
    # 스크롤바(있다면) 숨김
    viewer.image_display_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    viewer.image_display_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    # 직접 전체화면으로 전환 (애니메이션 최소화)
    viewer.showFullScreen()
    QTimer.singleShot(0, lambda: viewer.image_display_area.fit_to_window())


def exit_fullscreen(viewer):
    viewer.is_fullscreen = False

    # 안전한 방법으로 창 상태 복원 (제목표시줄 보장)
    if viewer.previous_window_state and viewer.previous_window_state['maximized']:
        viewer.showMaximized()
    else:
        viewer.showNormal()
        if viewer.previous_window_state:
            QTimer.singleShot(10, lambda: viewer.setGeometry(viewer.previous_window_state['geometry']))

    # 버튼 레이아웃 다시 표시
    if hasattr(viewer, 'button_bar') and viewer.button_bar:
        viewer.button_bar.show()

    # 상태바 표시
    viewer.statusBar().show()

    # 레이아웃 마진 복원
    try:
        l, t, r, b = viewer._normal_margins
        viewer.main_layout.setContentsMargins(l, t, r, b)
    except Exception:
        viewer.main_layout.setContentsMargins(5, 5, 5, 5)

    # 스크롤바 정책 복원: 필요 시 자동
    viewer.image_display_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    viewer.image_display_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    QTimer.singleShot(0, lambda: viewer.image_display_area.fit_to_window())


