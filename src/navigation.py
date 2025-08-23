def show_prev_image(viewer) -> None:
    if viewer.current_image_index > 0:
        viewer.current_image_index -= 1
        viewer.load_image_at_current_index()


def show_next_image(viewer) -> None:
    if viewer.current_image_index < len(viewer.image_files_in_dir) - 1:
        viewer.current_image_index += 1
        viewer.load_image_at_current_index()


def load_image_at_current_index(viewer) -> None:
    if 0 <= viewer.current_image_index < len(viewer.image_files_in_dir):
        viewer.load_image(viewer.image_files_in_dir[viewer.current_image_index], source='nav')


def update_button_states(viewer) -> None:
    num_images = len(viewer.image_files_in_dir)
    is_valid_index = 0 <= viewer.current_image_index < num_images

    viewer.prev_button.setEnabled(is_valid_index and viewer.current_image_index > 0)
    viewer.next_button.setEnabled(is_valid_index and viewer.current_image_index < num_images - 1)
    has_image = bool(viewer.load_successful)
    viewer.zoom_in_button.setEnabled(has_image)
    viewer.zoom_out_button.setEnabled(has_image)
    viewer.fit_button.setEnabled(has_image)


