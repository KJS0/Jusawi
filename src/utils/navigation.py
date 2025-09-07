class NavigationController:
    def __init__(self, viewer):
        self._viewer = viewer

    def can_prev(self) -> bool:
        return self._viewer.current_image_index > 0

    def can_next(self) -> bool:
        return self._viewer.current_image_index < len(self._viewer.image_files_in_dir) - 1

    def show_prev_image(self) -> None:
        viewer = self._viewer
        if viewer.current_image_index > 0:
            if getattr(viewer, "_is_dirty", False):
                if not viewer._handle_dirty_before_action():
                    return
            viewer.current_image_index -= 1
            viewer.load_image_at_current_index()

    def show_next_image(self) -> None:
        viewer = self._viewer
        if viewer.current_image_index < len(viewer.image_files_in_dir) - 1:
            if getattr(viewer, "_is_dirty", False):
                if not viewer._handle_dirty_before_action():
                    return
            viewer.current_image_index += 1
            viewer.load_image_at_current_index()

    def load_image_at_current_index(self) -> None:
        viewer = self._viewer
        if 0 <= viewer.current_image_index < len(viewer.image_files_in_dir):
            viewer.load_image(viewer.image_files_in_dir[viewer.current_image_index], source='nav')
            # 내비게이션으로 전환된 경우에도 원본 업그레이드를 확실히 예약
            try:
                if viewer.load_successful and not viewer._is_current_file_animation() and not getattr(viewer, "_movie", None):
                    if viewer._fullres_upgrade_timer.isActive():
                        viewer._fullres_upgrade_timer.stop()
                    # 빠른 전환 중 과도한 디코드 폭주 방지를 위해 약간의 텀
                    viewer._fullres_upgrade_timer.start(100)
                    # 다음 틱이 아닌, 약간의 텀 뒤 업그레이드 시도(키 꾹 누름 대비)
                    from PyQt6.QtCore import QTimer  # type: ignore[import]
                    QTimer.singleShot(100, getattr(viewer, "_upgrade_to_fullres_if_needed", lambda: None))
            except Exception:
                pass

    def update_button_states(self) -> None:
        viewer = self._viewer
        num_images = len(viewer.image_files_in_dir)
        is_valid_index = 0 <= viewer.current_image_index < num_images

        viewer.prev_button.setEnabled(is_valid_index and viewer.current_image_index > 0)
        viewer.next_button.setEnabled(is_valid_index and viewer.current_image_index < num_images - 1)
        has_image = bool(viewer.load_successful)
        viewer.zoom_in_button.setEnabled(has_image)
        viewer.zoom_out_button.setEnabled(has_image)
        viewer.fit_button.setEnabled(has_image)


def show_prev_image(viewer) -> None:
    if viewer.current_image_index > 0:
        # Dirty 확인은 viewer.load_image에서도 수행되나, 인덱스 롤백을 방지하려면 사전 확인이 더 안전
        if getattr(viewer, "_is_dirty", False):
            if not viewer._handle_dirty_before_action():
                return
        viewer.current_image_index -= 1
        viewer.load_image_at_current_index()


def show_next_image(viewer) -> None:
    if viewer.current_image_index < len(viewer.image_files_in_dir) - 1:
        if getattr(viewer, "_is_dirty", False):
            if not viewer._handle_dirty_before_action():
                return
        viewer.current_image_index += 1
        viewer.load_image_at_current_index()


def load_image_at_current_index(viewer) -> None:
    if 0 <= viewer.current_image_index < len(viewer.image_files_in_dir):
        viewer.load_image(viewer.image_files_in_dir[viewer.current_image_index], source='nav')
        # 함수형 경로에서도 동일하게 업그레이드 예약
        try:
            if viewer.load_successful and not viewer._is_current_file_animation() and not getattr(viewer, "_movie", None):
                if viewer._fullres_upgrade_timer.isActive():
                    viewer._fullres_upgrade_timer.stop()
                viewer._fullres_upgrade_timer.start(100)
                from PyQt6.QtCore import QTimer  # type: ignore[import]
                QTimer.singleShot(100, getattr(viewer, "_upgrade_to_fullres_if_needed", lambda: None))
        except Exception:
            pass


def update_button_states(viewer) -> None:
    num_images = len(viewer.image_files_in_dir)
    is_valid_index = 0 <= viewer.current_image_index < num_images

    viewer.prev_button.setEnabled(is_valid_index and viewer.current_image_index > 0)
    viewer.next_button.setEnabled(is_valid_index and viewer.current_image_index < num_images - 1)
    has_image = bool(viewer.load_successful)
    viewer.zoom_in_button.setEnabled(has_image)
    viewer.zoom_out_button.setEnabled(has_image)
    viewer.fit_button.setEnabled(has_image)


