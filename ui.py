import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QApplication, 
                             QLabel, QRubberBand, QMessageBox, QMenu, QAction)
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QCursor, QColor, QPainter, QPixmap, QPen

from core import capture_screen, process_and_translate_image

class TranslationWorker(QThread):
    """
    使用 QThread 在背景處理截圖與沉浸式翻譯，避免 UI 卡頓
    """
    # 定義發送訊號：(翻譯後的圖片路徑)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, rect, font_path='', font_family='', ocr_engine='windows',
                 translator_engine='google', img_path=None):
        super().__init__()
        self.rect = rect
        self.font_path = font_path
        self.font_family = font_family
        self.ocr_engine = ocr_engine
        self.translator_engine = translator_engine
        self.img_path = img_path

    def run(self):
        try:
            x, y = self.rect.x(), self.rect.y()
            w, h = self.rect.width(), self.rect.height()
            
            # 1. 畫面擷取
            img_path = self.img_path
            if not img_path:
                img_path = capture_screen(x, y, w, h)
            
            # 2. OCR 辨識、翻譯與影像合成
            out_img_path, err_msg = process_and_translate_image(
                img_path,
                font_path=self.font_path or None,
                font_family=self.font_family or None,
                ocr_engine=self.ocr_engine,
                translator_engine=self.translator_engine
            )
            
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
        # 確保視窗能接收鍵盤事件
        self.setFocusPolicy(Qt.StrongFocus)
        # 將滑鼠指標改為十字型
        self.setCursor(Qt.CrossCursor)

        # 取得所有螢幕組成的虛擬桌面總範圍（多螢幕環境下覆蓋所有螢幕）
        virtual_rect = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual_rect)

    def showEvent(self, event):
        super().showEvent(event)
        # 視窗顯示後立即搶焦點，確保能接收到 ESC 等鍵盤輸入
        self.activateWindow()
        self.setFocus()

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


class LoadingOverlayWindow(QWidget):
    """
    在 OCR 辨識期間顯示「辨識中...」的小視窗，覆蓋在使用者剛選取的範圍中央。
    """
    def __init__(self, target_rect):
        super().__init__()
        # 無邊框、置頂、不顯示在工作列
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        # 整個視窗半透明
        self.setWindowOpacity(0.85)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 標籤樣式：深色背景、白字、圓角
        self.label = QLabel("辨識中...")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                background-color: #333333;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 8px;
            }
        """)
        
        main_layout.addWidget(self.label)
        self.setLayout(main_layout)
        
        # 計算視窗大小並置中於 target_rect
        self.adjustSize()
        w = self.width()
        h = self.height()
        
        # 將自己擺在目標框的正中央
        cx = target_rect.x() + target_rect.width() // 2
        cy = target_rect.y() + target_rect.height() // 2
        self.move(cx - w // 2, cy - h // 2)

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
        # 透明背景：讓視窗可以覆蓋整個桌面但只顯示圖片
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 確保視窗能接收鍵盤事件
        self.setFocusPolicy(Qt.StrongFocus)
        
        # image_label 用絕對定位，不使用 layout
        self.image_label = QLabel(self)
        self.image_label.setCursor(Qt.PointingHandCursor)
        
        # 縮放相關狀態
        self.original_pixmap = None
        self.scale_factor = 1.0
        self.original_x = 0
        self.original_y = 0

        # 拖曳相關狀態
        self.drag_start_pos = None

    def set_image(self, image_path, target_rect):
        """
        設定並顯示翻譯好的圖片。
        視窗覆蓋整個虛擬桌面（透明），點擊任何地方都可關閉。
        圖片以絕對座標貼在原始位置。
        """
        pixmap = QPixmap(image_path)
        
        # 在圖片邊緣繪製紅色外框
        border_width = 3
        painter = QPainter(pixmap)
        pen = QPen(QColor(220, 30, 30))
        pen.setWidth(border_width)
        painter.setPen(pen)
        painter.drawRect(
            border_width // 2,
            border_width // 2,
            pixmap.width() - border_width,
            pixmap.height() - border_width
        )
        painter.end()
        
        self.original_pixmap = pixmap
        self.scale_factor = 1.0
        
        self.image_label.setPixmap(pixmap)
        self.image_label.setFixedSize(pixmap.size())
        
        # 視窗覆蓋整個虛擬桌面（多螢幕合併）
        virtual_rect = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual_rect)
        
        # 圖片位置：target_rect 相對於虛擬桌面左上角的偏移
        self.original_x = target_rect.x() - virtual_rect.x()
        self.original_y = target_rect.y() - virtual_rect.y()
        self.image_label.move(self.original_x, self.original_y)
        
        self.show()
        self.activateWindow()
        self.setFocus()

    def paintEvent(self, event):
        # Windows 上 alpha=0 的區域會穿透滑鼠事件
        # 用幾乎不可見的底色（alpha=1）填滿，確保整個視窗都能接收點擊
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

    def keyPressEvent(self, event):
        # 按下 ESC 關閉此 overlay，程式繼續在系統列執行
        if event.key() == Qt.Key_Escape:
            self.hide()

    def wheelEvent(self, event):
        """
        支援滑鼠滾輪縮放圖片
        """
        if not self.original_pixmap:
            return
            
        # 判斷滾輪方向 (angleDelta().y() > 0 代表往上滾/放大)
        delta = event.angleDelta().y()
        if delta > 0:
            self.scale_factor *= 1.15
        elif delta < 0:
            self.scale_factor /= 1.15
            
        # 限制縮放極限 (0.2x 到 10.0x)
        self.scale_factor = max(0.2, min(self.scale_factor, 10.0))
        
        self._update_image_geometry()

    def _update_image_geometry(self):
        """
        根據目前的 scale_factor 重新縮放圖片並置中於原始中心點
        """
        if not self.original_pixmap:
            return
            
        # 計算新的尺寸
        new_width = int(self.original_pixmap.width() * self.scale_factor)
        new_height = int(self.original_pixmap.height() * self.scale_factor)
        
        # 套用高品質縮放
        scaled_pixmap = self.original_pixmap.scaled(
            new_width, new_height,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setFixedSize(scaled_pixmap.size())
        
        # 保持中心點不變
        orig_center_x = self.original_x + self.original_pixmap.width() / 2
        orig_center_y = self.original_y + self.original_pixmap.height() / 2
        
        new_x = int(orig_center_x - new_width / 2)
        new_y = int(orig_center_y - new_height / 2)
        
        self.image_label.move(new_x, new_y)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 檢查點擊是否在翻譯圖片的範圍內
            if self.image_label.geometry().contains(event.pos()):
                # 在圖片內：開始拖曳
                self.drag_start_pos = event.pos() - self.image_label.pos()
            else:
                # 在圖片外：關閉 overlay
                self.hide()
        elif event.button() == Qt.RightButton:
            # 右鍵：顯示操作選單
            menu = QMenu(self)
            action_copy = QAction("複製圖片", self)
            action_close = QAction("關閉", self)
            menu.addAction(action_copy)
            menu.addSeparator()
            menu.addAction(action_close)

            action_copy.triggered.connect(self._copy_to_clipboard)
            action_close.triggered.connect(self.hide)

            menu.exec_(event.globalPos())

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is not None and (event.buttons() & Qt.LeftButton):
            # 左鍵拖曳中
            new_pos = event.pos() - self.drag_start_pos
            self.image_label.move(new_pos)
            
            # 更新 original_x 和 original_y 讓後續滾輪縮放時中心點維持正確
            cur_width = self.image_label.width()
            cur_height = self.image_label.height()
            cur_center_x = new_pos.x() + cur_width / 2.0
            cur_center_y = new_pos.y() + cur_height / 2.0
            
            self.original_x = cur_center_x - self.original_pixmap.width() / 2.0
            self.original_y = cur_center_y - self.original_pixmap.height() / 2.0

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = None

    def _copy_to_clipboard(self):
        """將目前顯示的翻譯圖片複製到系統剪貼簿"""
        pixmap = self.image_label.pixmap()
        if pixmap:
            QApplication.clipboard().setPixmap(pixmap)

    def closeEvent(self, event):
        # 只隱藏視窗，不退出整個程式
        self.hide()
        event.ignore()
