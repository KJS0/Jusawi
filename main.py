import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QFileDialog
from PyQt6.QtGui import QPixmap, QColor, QPainter
from PyQt6.QtCore import Qt, QTimer, QSize

class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(1, 1) # 위젯이 매우 작아질 수 있도록 최소 크기 설정
        self.pixmap = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter) # 이미지를 중앙에 정렬

    def setPixmap(self, pixmap):
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

        size = self.size()
        scaled_pixmap = self.pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        # 이미지를 중앙에 배치
        x = (size.width() - scaled_pixmap.width()) / 2
        y = (size.height() - scaled_pixmap.height()) / 2
        painter.drawPixmap(int(x), int(y), scaled_pixmap)

    def sizeHint(self):
        return QSize(640, 480)

class JusawiViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jusawi") # 창 제목

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # 레이아웃 여백 제거

        self.image_display_area = ImageLabel(self)
        layout.addWidget(self.image_display_area)
        self.setLayout(layout)

        # 프로그램 시작 시 파일 열기 대화상자 실행 및 결과 확인
        if not self.open_file_dialog():
            QTimer.singleShot(0, self.close) 

    def open_file_dialog(self):
        file_filter = "사진 (*.jpeg *.jpg *.png *.bmp *.gif *.tiff)"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "사진 파일 열기",
            "", # 기본 경로 (비워두면 마지막 사용 경로 또는 기본 문서 폴더)
            file_filter
        )

        if file_path:
            pixmap = QPixmap(file_path)
            if pixmap.isNull(): # 이미지 로드 실패
                print(f"오류: 이미지를 불러올 수 없습니다. {file_path}")
                return False
            else:
                self.image_display_area.setPixmap(pixmap)
                return True
        else: # 사용자가 파일 선택을 취소한 경우
            print("이미지를 선택하지 않았습니다. 프로그램을 종료합니다.")
            return False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = JusawiViewer()
    viewer.show()
    sys.exit(app.exec())