import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QApplication, 
                             QLabel, QRubberBand, QMessageBox)
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QCursor, QColor, QPainter, QPixmap

from core import capture_screen, process_and_translate_image

class TranslationWorker(QThread):
    """
    使用 QThread 在背景處理截圖與沉浸式翻譯，避免 UI 卡頓
    """
    # 定義發送訊號：(翻譯後的圖片路徑)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, rect):
        super().__init__()
        self.rect = rect

    def run(self):
        try:
            x, y = self.rect.x(), self.rect.y()
            w, h = self.rect.width(), self.rect.height()
            
            # 1. 畫面擷取
            img_path = capture_screen(x, y, w, h)
            
            # 2. OCR 辨識、翻譯與影像合成
            out_img_path, err_msg = process_and_translate_image(img_path)
            
            if err_msg:
                self.error.emit(err_msg)
            else:
                self.finished.emit(out_img_path)
            
        except Exception as e:
            self.error.emit(f"發生未知的錯誤: {str(e)}")


class SelectionWindow(QWidget):
    """
    全螢幕、半透明且無邊框的選取視窗，支援滑鼠拖曳框選範圍
    """
    selection_completed = pyqtSignal(QRect)
    selection_cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.origin = QPoint()
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        self.initUI()

    def initUI(self):
        # 設置無邊框與置頂
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        # 背景透明化，以便自己繪製半透明遮罩
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 將滑鼠指標改為十字型
        self.setCursor(Qt.CrossCursor)

        # 取得所有螢幕範圍並設置為全螢幕
        screen_rect = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_rect)

    def paintEvent(self, event):
        """
        繪製半透明遮罩，便於使用者區分選取狀態
        """
        painter = QPainter(self)
        # 繪製黑色且透明度 100/255 的遮罩背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubberBand.setGeometry(QRect(self.origin, QSize()))
            self.rubberBand.show()

    def mouseMoveEvent(self, event):
        if not self.origin.isNull():
            # 動態更新選取框的大小時自動正規化以支援往各個方向拖曳
            self.rubberBand.setGeometry(QRect(self.origin, event.pos()).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            rect = self.rubberBand.geometry()
            self.rubberBand.hide()
            
            # 隱藏視窗以便截圖時畫面不包含灰色的遮罩
            self.hide()
            
            # 確保有實際選取範圍 (寬高大於 10 像素)
            if rect.width() > 10 and rect.height() > 10:
                # 若有多螢幕，轉換為全域座標以保證截圖座標無誤
                global_rect = QRect(self.mapToGlobal(rect.topLeft()), rect.size())
                self.selection_completed.emit(global_rect)
            else:
                self.selection_cancelled.emit()

    def keyPressEvent(self, event):
        # 按下 ESC 鍵可取消選取並關閉
        if event.key() == Qt.Key_Escape:
            self.hide()
            self.selection_cancelled.emit()


class ImageOverlayWindow(QWidget):
    """
    就地圖片翻譯顯示視窗：無邊框、將翻譯好的圖片直接貼回螢幕上原來的位置。
    """
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # 設置無邊框、置頂與 Tool 屬性 (避免出現在工作列)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        
        # 主版面佈局：零邊距以完全貼齊圖片
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_label = QLabel()
        # 設定滑鼠指標為手型提示使用者可點擊關閉
        self.image_label.setCursor(Qt.PointingHandCursor) 
        
        main_layout.addWidget(self.image_label)
        self.setLayout(main_layout)

    def set_image(self, image_path, target_rect):
        """
        設定並顯示翻譯好的圖片，視窗將完全蓋住原來的區域
        """
        pixmap = QPixmap(image_path)
        self.image_label.setPixmap(pixmap)
        
        self.setGeometry(target_rect)
        self.show()
        self.activateWindow()

    def mousePressEvent(self, event):
        # 點擊圖片的任何位置都會直接關閉退出程式
        if event.button() == Qt.LeftButton:
            QApplication.quit()

    def closeEvent(self, event):
        QApplication.quit()
        event.accept()
