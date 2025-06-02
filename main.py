import sys
import os
import ctypes # Only for Windows
import functools
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog, QPushButton
from PyQt6.QtGui import QPixmap, QColor, QPainter
from PyQt6.QtCore import Qt, QTimer, QSize

shlwapi = ctypes.WinDLL('shlwapi')
strcmplogicalw = shlwapi.StrCmpLogicalW
strcmplogicalw.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
strcmplogicalw.restype = ctypes.c_int

class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(1, 1) # 위젯이 매우 작아질 수 있도록 최소 크기 설정
        self.pixmap = None # 이미지 저장
        self.setAlignment(Qt.AlignmentFlag.AlignCenter) # 이미지를 중앙에 정렬

    def setPixmap(self, pixmap): # 이미지 설정
        if pixmap and not pixmap.isNull():
            self.pixmap = pixmap
        else:
            self.pixmap = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#333333")) # 배경색 설정

        if not self.pixmap or self.pixmap.isNull():
            return

        # 이미지 크기 조정
        size = self.size()
        scaled_pixmap = self.pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        # 이미지를 중앙에 배치
        x = (size.width() - scaled_pixmap.width()) / 2
        y = (size.height() - scaled_pixmap.height()) / 2

        # 이미지 그리기
        painter.drawPixmap(int(x), int(y), scaled_pixmap)

    def sizeHint(self):
        return QSize(480, 320)

class JusawiViewer(QWidget):
    SUPPORTED_FORMATS = [".jpeg", ".jpg", ".png", ".bmp", ".gif", ".tiff"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jusawi") # 창 제목

        self.current_image_path = None
        self.image_files_in_dir = []
        self.current_image_index = -1

        main_layout = QVBoxLayout(self) # 전체 레이아웃
        main_layout.setContentsMargins(5, 5, 5, 5) # 레이아웃 여백

        self.image_display_area = ImageLabel(self)
        main_layout.addWidget(self.image_display_area, 1)

        # 버튼 레이아웃 구현
        button_layout = QHBoxLayout()
        self.prev_button = QPushButton("이전")
        self.next_button = QPushButton("다음")
        self.prev_button.clicked.connect(self.show_prev_image)
        self.next_button.clicked.connect(self.show_next_image)
        
        button_layout.addStretch(1) # 버튼들을 중앙 또는 오른쪽으로 밀기 위한 stretch
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.next_button)
        button_layout.addStretch(1)

        main_layout.addLayout(button_layout) # 메인 레이아웃에 추가
        self.setLayout(main_layout)

        self.update_button_states() # 초기 버튼 상태 업데이트
        
        if not self.open_file_dialog():
            QTimer.singleShot(0, self.close)

    def open_file_dialog(self):
        file_filter = f"사진 ({' '.join(['*' + ext for ext in self.SUPPORTED_FORMATS])})"
        file_path, _ = QFileDialog.getOpenFileName(self, "사진 파일 열기", "", file_filter)

        if file_path:
            return self.load_image(file_path)
        else:
            print("이미지를 선택하지 않았습니다. 프로그램을 종료합니다.")
            return False

    def load_image(self, file_path):
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            print(f"오류: 이미지를 불러올 수 없습니다. {file_path}")
            self.image_display_area.setPixmap(None)
            self.current_image_path = None
            self.image_files_in_dir = []
            self.current_image_index = -1
            self.update_button_states()
            return False # 로드 실패 시 open_file_dialog의 결과에 영향
        
        self.image_display_area.setPixmap(pixmap)
        self.current_image_path = file_path
        if os.path.exists(file_path):
             self.scan_directory(os.path.dirname(file_path))
        return True

    def scan_directory(self, dir_path):
        self.image_files_in_dir = []
        new_index = -1
        
        normalized_current_path = None
        if self.current_image_path:
            normalized_current_path = os.path.normcase(self.current_image_path)

        try:
            raw_files = os.listdir(dir_path)
            # Windows 탐색기 스타일로 파일 이름 정렬
            sorted_filenames = sorted(raw_files, key=functools.cmp_to_key(lambda item1, item2: strcmplogicalw(item1, item2)))
            
            temp_file_list = []
            for fname in sorted_filenames:
                if os.path.splitext(fname.lower())[1] in self.SUPPORTED_FORMATS:
                    full_path = os.path.join(dir_path, fname)
                    temp_file_list.append(full_path)
                    # 정규화된 경로로 현재 이미지 경로와 비교하여 인덱스 찾기
                    if normalized_current_path and os.path.normcase(full_path) == normalized_current_path:
                        new_index = len(temp_file_list) - 1 # 찾았으면 인덱스 기록
            
            self.image_files_in_dir = temp_file_list
            self.current_image_index = new_index

            # (선택적 디버깅) 만약 현재 이미지를 목록에서 못 찾았을 경우 경고 출력
            if self.current_image_index == -1 and self.current_image_path and self.image_files_in_dir:
                print(f"경고: 현재 로드된 이미지 '{self.current_image_path}'를 해당 디렉토리의 스캔 목록에서 정확히 찾지 못했습니다. 경로를 확인해주세요.")

        except OSError as e:
            print(f"디렉토리 스캔 중 오류 발생: {e}")
            self.image_files_in_dir = [] # 오류 시 목록 비우기
            self.current_image_index = -1 # 오류 시 인덱스 초기화
        
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
        # current_image_index가 유효한 범위 (0 이상이고, 목록 크기 미만)에 있는지 확인
        is_valid_index = 0 <= self.current_image_index < num_images
        
        self.prev_button.setEnabled(is_valid_index and self.current_image_index > 0)
        self.next_button.setEnabled(is_valid_index and self.current_image_index < num_images - 1)
            
if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = JusawiViewer()
    viewer.show()
    sys.exit(app.exec())