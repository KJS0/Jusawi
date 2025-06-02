from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap, QColor, QPainter
from PyQt6.QtCore import Qt, QSize

class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(1, 1) 
        self.pixmap = None 
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def setPixmap(self, pixmap): 
        if pixmap and not pixmap.isNull():
            self.pixmap = pixmap
        else:
            self.pixmap = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#333333"))

        if not self.pixmap or self.pixmap.isNull():
            return

        size = self.size()
        scaled_pixmap = self.pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        x = (size.width() - scaled_pixmap.width()) / 2
        y = (size.height() - scaled_pixmap.height()) / 2
        painter.drawPixmap(int(x), int(y), scaled_pixmap)

    def sizeHint(self):
        return QSize(480, 320)