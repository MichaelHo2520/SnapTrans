import sys
import ctypes
import keyboard
from PyQt5.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QIcon, QPixmap, QColor
from ui import SelectionWindow, ImageOverlayWindow, TranslationWorker

def set_dpi_awareness():
    """
    DPI 系統感知：確保後續抓取的螢幕座標絕對精準。
    """
    if sys.platform == 'win32':
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


class HotkeyThread(QThread):
    """
    在背景監聽全域快捷鍵的執行緒，當觸發時透過 signal 通知主畫面彈出
    """
    hotkey_triggered = pyqtSignal()

    def run(self):
        # 註冊全域快捷鍵 Ctrl+F1
        # 添加 suppress=False 避免干擾其他軟體的快速鍵如果發生衝突
        keyboard.add_hotkey('ctrl+f1', self.on_hotkey)
        # 讓執行緒持續等待直到被終止
        keyboard.wait()
        
    def on_hotkey(self):
        self.hotkey_triggered.emit()


# 載入資源檔
HAS_EMBEDDED_ICON = False
try:
    import icon_data
    HAS_EMBEDDED_ICON = True
except ImportError:
    pass

class SnapTransApp:
    def __init__(self):
        self.selection_window = None
        self.result_window = None
        self.worker = None
        self.target_rect = None
        
        # 建立系統列圖示
        tray_icon_img = QIcon()
        if HAS_EMBEDDED_ICON and hasattr(icon_data, 'ICON_PNG_BYTES'):
            pixmap = QPixmap()
            pixmap.loadFromData(icon_data.ICON_PNG_BYTES)
            tray_icon_img = QIcon(pixmap)
        
        self.tray_icon = QSystemTrayIcon(tray_icon_img, QApplication.instance())
        self.tray_icon.setToolTip("SnapTrans 沉浸式翻譯工具 (Ctrl+F1)")
        
        # 建立右鍵選單
        self.menu = QMenu()
        
        self.action_translate = QAction("開始翻譯 (Ctrl+F1)")
        self.action_translate.triggered.connect(self.start_selection)
        
        self.action_quit = QAction("退出程式")
        self.action_quit.triggered.connect(self.quit_app)
        
        self.menu.addAction(self.action_translate)
        self.menu.addSeparator()
        self.menu.addAction(self.action_quit)
        
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
        
        # 啟動快捷鍵監聽執行緒
        self.hotkey_thread = HotkeyThread()
        self.hotkey_thread.hotkey_triggered.connect(self.start_selection)
        self.hotkey_thread.start()

    def run(self):
        """
        啟動應用程式。現在只會駐留在系統列，不會在一開始顯示選取視窗。
        可以選擇顯示一個氣泡提示告訴使用者程式已經啟動。
        """
        self.tray_icon.showMessage(
            "SnapTrans 啟動成功",
            "工具已在背景執行。\n請按下 Ctrl+F1 或點擊右鍵選單開始截圖翻譯。",
            QSystemTrayIcon.Information,
            3000
        )

    def start_selection(self):
        """
        開始進行截圖框選
        """
        # 如果已經在選取狀態或已經顯示結果，將其關閉重製
        if self.selection_window:
            self.selection_window.close()
            self.selection_window.deleteLater()
            
        if self.result_window:
            self.result_window.close()
            self.result_window.deleteLater()
            self.result_window = None
            
        self.selection_window = SelectionWindow()
        self.selection_window.selection_completed.connect(self.on_selection_completed)
        self.selection_window.selection_cancelled.connect(self.on_selection_cancelled)
        self.selection_window.show()

    def on_selection_cancelled(self):
        """
        當使用者取消選取（點擊空白後放開或按ESC）時，只關閉遮罩，不退出程式
        """
        self.selection_window.close()
        self.selection_window.deleteLater()
        self.selection_window = None

    def on_selection_completed(self, rect):
        """
        使用者完成選取後觸發，啟用 QThread 背景翻譯，並改變滑鼠游標狀態以提示載入中。
        """
        self.target_rect = rect
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        self.worker = TranslationWorker(rect)
        self.worker.finished.connect(self.on_translation_finished)
        self.worker.error.connect(self.on_translation_error)
        self.worker.start()

    def on_translation_finished(self, out_img_path):
        """
        當背景翻譯與影像處理成功後觸發，顯示翻譯好的圖片
        """
        QApplication.restoreOverrideCursor()
        
        if not self.result_window:
            self.result_window = ImageOverlayWindow()
            
        self.result_window.set_image(out_img_path, self.target_rect)
        
        self.selection_window.close()
        self.selection_window.deleteLater()
        self.selection_window = None

    def on_translation_error(self, error_msg):
        """
        翻譯或 OCR 過程發生錯誤或找不到文字時觸發，彈出錯誤提示
        """
        QApplication.restoreOverrideCursor()
        QMessageBox.warning(None, "發生錯誤", error_msg)
        
        self.selection_window.close()
        self.selection_window.deleteLater()
        self.selection_window = None

    def quit_app(self):
        """完全退出程式，停止監聽執行緒"""
        # keyboard 庫終止監聽
        keyboard.unhook_all()
        # 隱藏系統圖標
        self.tray_icon.hide()
        QApplication.quit()


if __name__ == '__main__':
    # 1. 在建立 QApplication 之前務必設定好 DPI 感知
    set_dpi_awareness()
    
    # 2. 初始化 PyQt5 應用程式
    app = QApplication(sys.argv)
    
    # 載入 Window Icon
    if HAS_EMBEDDED_ICON and hasattr(icon_data, 'ICON_PNG_BYTES'):
        pixmap = QPixmap()
        pixmap.loadFromData(icon_data.ICON_PNG_BYTES)
        app.setWindowIcon(QIcon(pixmap))
    
    # 防止 selection_window 隱藏時觸發自動關閉應用程式的情境
    # 設定為 False 可以確保即使所有視窗關閉，程式仍會在背景透過 Tray Icon 存活
    app.setQuitOnLastWindowClosed(False)
    
    # 3. 執行主程式核心邏輯
    snap_app = SnapTransApp()
    snap_app.run()
    
    sys.exit(app.exec_())
