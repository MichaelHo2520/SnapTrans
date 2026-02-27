import sys
import ctypes
import keyboard
from PyQt5.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMenu, QAction, QFontDialog
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QIcon, QPixmap, QColor, QFont
from ui import SelectionWindow, ImageOverlayWindow, TranslationWorker, LoadingOverlayWindow
import config as cfg_module

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
        keyboard.add_hotkey('ctrl+f1', self.on_hotkey)
        # 讓執行緒持續等待直到被終止；捕捉例外避免程式崩潰
        try:
            keyboard.wait()
        except (KeyboardInterrupt, SystemExit):
            pass

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
        self.loading_window = None
        self.worker = None
        self.target_rect = None
        
        # 載入設定
        self._cfg = cfg_module.load_config()
        self.font_path = self._cfg.get('font_path', '')
        self.font_family = self._cfg.get('font_family', '')
        
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
        
        # 版本資訊（置頂，不可點擊）
        self.action_version = QAction("SnapTrans  V1.00")
        self.action_version.setEnabled(False)
        
        self.action_translate = QAction("開始翻譯 (Ctrl+F1)")
        self.action_translate.triggered.connect(self.start_selection)
        
        self.action_font = QAction("設定字體...")
        self.action_font.triggered.connect(self.open_font_settings)
        
        self.action_quit = QAction("退出程式")
        self.action_quit.triggered.connect(self.quit_app)
        
        self.menu.addAction(self.action_version)
        self.menu.addSeparator()
        self.menu.addAction(self.action_translate)
        self.menu.addAction(self.action_font)
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
            
        if self.loading_window:
            self.loading_window.close()
            self.loading_window.deleteLater()
            self.loading_window = None
            
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
        
        # 顯示「辨識中...」
        self.loading_window = LoadingOverlayWindow(rect)
        self.loading_window.show()
        
        self.worker = TranslationWorker(rect, font_path=self.font_path, font_family=self.font_family)
        self.worker.finished.connect(self.on_translation_finished)
        self.worker.error.connect(self.on_translation_error)
        self.worker.start()

    def open_font_settings(self):
        """開啟字體選擇對話框，儲存至 config.json"""
        # 建立当前已設定字體的預視 QFont
        current_family = self._cfg.get('font_family', '')
        initial_font = QFont(current_family) if current_family else QFont()
        
        font, ok = QFontDialog.getFont(initial_font, None, "選擇翻譯字體")
        if not ok:
            return
        
        family = font.family()
        # 搜尋對應的字型檔路徑
        path = cfg_module.find_font_path(family)
        
        self._cfg['font_family'] = family
        self._cfg['font_path'] = path
        self.font_path = path
        self.font_family = family
        cfg_module.save_config(self._cfg)
        
        # 小提示確認
        display = f"字體已設為：{family}"
        if not path:
            display += "\n（找不到對應的字型檔，將使用預設字體）"
        self.tray_icon.showMessage("字體設定", display,
                                   QSystemTrayIcon.Information, 2500)

    def on_translation_finished(self, out_img_path):
        """
        當背景翻譯與影像處理成功後觸發，顯示翻譯好的圖片
        """
        QApplication.restoreOverrideCursor()
        
        # 關閉載入提示
        if self.loading_window:
            self.loading_window.close()
            self.loading_window.deleteLater()
            self.loading_window = None
        
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
        
        # 關閉載入提示
        if self.loading_window:
            self.loading_window.close()
            self.loading_window.deleteLater()
            self.loading_window = None
            
        QMessageBox.warning(None, "發生錯誤", error_msg)
        
        self.selection_window.close()
        self.selection_window.deleteLater()
        self.selection_window = None

    def quit_app(self):
        """完全退出程式，停止監聽執行緒"""
        try:
            keyboard.unhook_all()
        except Exception:
            pass
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
