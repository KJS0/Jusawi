import sys
from PyQt6.QtWidgets import QApplication
from src.main_window import JusawiViewer 

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = JusawiViewer()
    viewer.show()
    sys.exit(app.exec())