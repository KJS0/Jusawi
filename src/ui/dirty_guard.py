from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox  # type: ignore[import]


def handle_dirty_before_action(viewer) -> bool:
    policy = getattr(viewer, "_save_policy", 'discard')
    if policy == 'discard':
        return True
    if policy == 'overwrite':
        return viewer.save_current_image()
    if policy == 'save_as':
        return viewer.save_current_image_as()
    box = QMessageBox(viewer)
    box.setWindowTitle("변경 내용 저장")
    box.setText("회전/뒤집기 변경 내용을 저장하시겠습니까?")
    btn_save = box.addButton("저장", QMessageBox.ButtonRole.AcceptRole)
    btn_save_as = box.addButton("다른 이름으로", QMessageBox.ButtonRole.ActionRole)
    btn_discard = box.addButton("무시", QMessageBox.ButtonRole.DestructiveRole)
    btn_cancel = box.addButton("취소", QMessageBox.ButtonRole.RejectRole)
    box.setIcon(QMessageBox.Icon.Question)
    box.exec()
    clicked = box.clickedButton()
    if clicked == btn_save:
        return viewer.save_current_image()
    if clicked == btn_save_as:
        return viewer.save_current_image_as()
    if clicked == btn_discard:
        return True
    return False


