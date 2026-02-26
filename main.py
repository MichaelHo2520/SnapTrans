import sys
import ctypes
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from ui import SelectionWindow, ImageOverlayWindow, TranslationWorker

def set_dpi_awareness():
    """
    DPI 系統感知：
    在程式最開頭呼叫 Windows API 處理高解析度螢幕（如 4K 或 150% 縮放）的縮放問題，
    確保後續抓取的螢幕座標絕對精準（不會因此而偏移或截圖錯位）。
    """
    if sys.platform == 'win32':
        try:
            # 優先嘗試 Windows 8.1 之後的 DPI 感知設定 (PROCESS_PER_MONITOR_DPI_AWARE)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                # 替補方案：Windows Vista 之後的系統
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

class SnapTransApp:
    def __init__(self):
        self.selection_window = None
        self.result_window = None
        self.worker = None
        self.target_rect = None

    def run(self):
        """
        啟動應用程式並顯示選取視窗
        """
        self.selection_window = SelectionWindow()
        self.selection_window.selection_completed.connect(self.on_selection_completed)
        self.selection_window.selection_cancelled.connect(self.on_selection_cancelled)
        self.selection_window.show()

    def on_selection_cancelled(self):
        """
        當使用者取消選取（點擊空白後放開或按ESC）時，關閉並退出程式
        """
        QApplication.quit()

    def on_selection_completed(self, rect):
        """
        使用者完成選取後觸發，啟用 QThread 背景翻譯，並改變滑鼠游標狀態以提示載入中。
        """
        # 儲存選取的座標用於後續顯示結果
        self.target_rect = rect
        
        # 選取視窗已經在釋放滑鼠時隱藏了，避免截圖拍到 UI
        
        # 將全域滑鼠游標設定為讀取狀態（沙漏或旋轉圈圈）
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        # 啟動背景執行緒執行截圖、OCR與翻譯，防止主執行緒介面卡頓
        self.worker = TranslationWorker(rect)
        self.worker.finished.connect(self.on_translation_finished)
        self.worker.error.connect(self.on_translation_error)
        self.worker.start()

    def on_translation_finished(self, out_img_path):
        """
        當背景翻譯與影像處理成功後觸發，顯示翻譯好的圖片
        """
        # 恢復正常游標
        QApplication.restoreOverrideCursor()
        
        # 建立專屬圖片顯示視窗
        if not self.result_window:
            self.result_window = ImageOverlayWindow()
            
        # 傳遞翻譯完畢的圖片路徑與一開始選取的座標方塊
        self.result_window.set_image(out_img_path, self.target_rect)
        
        # 視窗已經建立並顯示，現在可以釋放選取視窗的資源
        self.selection_window.close()

    def on_translation_error(self, error_msg):
        """
        翻譯或 OCR 過程發生錯誤或找不到文字時觸發，彈出錯誤提示
        """
        # 恢復正常游標
        QApplication.restoreOverrideCursor()
        
        # 顯示警告畫面區塊
        QMessageBox.warning(None, "發生錯誤", error_msg)
        
        # 關閉並釋放選取視窗，強制結束程式
        self.selection_window.close()
        QApplication.quit()

if __name__ == '__main__':
    # 1. 在建立 QApplication 之前務必設定好 DPI 感知
    set_dpi_awareness()
    
    # 2. 初始化 PyQt5 應用程式
    app = QApplication(sys.argv)
    
    # 防止 selection_window 隱藏時觸發自動關閉應用程式的情境
    # 因為我們會在背景執行完畢後才決定要顯示 ImageOverlayWindow 或因出錯而主動退出
    app.setQuitOnLastWindowClosed(False)
    
    # 3. 執行主程式核心邏輯
    snap_app = SnapTransApp()
    snap_app.run()
    
    sys.exit(app.exec_())
