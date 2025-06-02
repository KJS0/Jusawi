import os
import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import QTimer

from .image_label import ImageLabel
from .file_utils import open_file_dialog_util, load_image_util, scan_directory_util

class JusawiViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jusawi")

        self.current_image_path = None
        self.image_files_in_dir = []
        self.current_image_index = -1
        self.load_successful = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self.image_display_area = ImageLabel(self)
        main_layout.addWidget(self.image_display_area, 1)

        button_layout = QHBoxLayout()
        self.prev_button = QPushButton("이전")
        self.next_button = QPushButton("다음")
        self.prev_button.clicked.connect(self.show_prev_image)
        self.next_button.clicked.connect(self.show_next_image)
        
        button_layout.addStretch(1)
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.next_button)
        button_layout.addStretch(1)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

        self.update_button_states()
        
        self.load_successful = self.open_file_and_load_initial_image()
        if not self.load_successful:
            QTimer.singleShot(0, self.close)

    def open_file_and_load_initial_image(self):
        file_path = open_file_dialog_util(self)
        if file_path:
            return self.load_image(file_path)
        else:
            print("이미지를 선택하지 않았습니다. 프로그램을 종료합니다.")
            return False

    def load_image(self, file_path):
        loaded_path, success = load_image_util(file_path, self.image_display_area)
        if not success:
            self.current_image_path = None
            self.image_files_in_dir = []
            self.current_image_index = -1
        else:
            self.current_image_path = loaded_path
            if os.path.exists(file_path):
                 self.scan_directory(os.path.dirname(file_path))
        self.update_button_states()
        return success

    def scan_directory(self, dir_path):
        self.image_files_in_dir, self.current_image_index = scan_directory_util(dir_path, self.current_image_path)
        self.update_button_states()

    def show_prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.load_image_at_current_index()

    def show_next_image(self):
        if self.current_image_index < len(self.image_files_in_dir) - 1:
            self.current_image_index += 1
            self.load_image_at_current_index()

    def load_image_at_current_index(self):
        if 0 <= self.current_image_index < len(self.image_files_in_dir):
            self.load_image(self.image_files_in_dir[self.current_image_index])

    def update_button_states(self):
        num_images = len(self.image_files_in_dir)
        is_valid_index = 0 <= self.current_image_index < num_images
        
        self.prev_button.setEnabled(is_valid_index and self.current_image_index > 0)
        self.next_button.setEnabled(is_valid_index and self.current_image_index < num_images - 1)