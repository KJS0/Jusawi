from PyQt6.QtGui import QKeySequence, QShortcut


def setup_shortcuts(viewer) -> None:
    # ← / → : 이전/다음 이미지
    QShortcut(QKeySequence("Left"), viewer, viewer.show_prev_image)
    QShortcut(QKeySequence("Right"), viewer, viewer.show_next_image)

    # Ctrl + O : 파일 열기
    QShortcut(QKeySequence("Ctrl+O"), viewer, viewer.open_file)

    # F11 : 전체화면 토글
    QShortcut(QKeySequence("F11"), viewer, viewer.toggle_fullscreen)

    # Esc : 전체화면 종료 또는 프로그램 종료
    QShortcut(QKeySequence("Escape"), viewer, viewer.handle_escape)

    # Del : 현재 이미지 삭제
    QShortcut(QKeySequence("Delete"), viewer, viewer.delete_current_image)

    # 보기 모드 단축키
    QShortcut(QKeySequence("F"), viewer, viewer.fit_to_window)
    QShortcut(QKeySequence("W"), viewer, viewer.fit_to_width)
    QShortcut(QKeySequence("H"), viewer, viewer.fit_to_height)
    QShortcut(QKeySequence("1"), viewer, viewer.reset_to_100)

    # 주의: Ctrl +/-/0 단축키는 제거됨


