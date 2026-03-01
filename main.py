import sys
import ctypes
import keyboard
import signal
from PyQt5.QtWidgets import (QApplication, QMessageBox, QSystemTrayIcon,
                             QMenu, QAction, QFontDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QIcon, QPixmap, QColor, QFont
from ui import SelectionWindow, ImageOverlayWindow, TranslationWorker, LoadingOverlayWindow
from core import capture_screen
import config as cfg_module
import updater

__version__ = "v1.0.1"


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
        self.font_path          = self._cfg.get('font_path', '')
        self.font_family        = self._cfg.get('font_family', '')
        self.ocr_engine         = self._cfg.get('ocr_engine', 'windows')
        self.translator_engine  = self._cfg.get('translator_engine', 'google')
        
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
        self.action_version = QAction(f"SnapTrans {__version__}")
        self.action_version.setEnabled(False)
        
        self.action_update = QAction("檢查更新", self.menu)
        self.action_update.triggered.connect(lambda: updater.check_for_updates(self, __version__))
        
        self.action_translate = QAction("開始翻譯 (Ctrl+F1)")
        self.action_translate.triggered.connect(self.start_selection)
        
        self.action_font = QAction("設定字體...")
        self.action_font.triggered.connect(self.open_font_settings)
        
        # OCR 引擎選擇 (次選單)
        self.menu_engine = QMenu("字元辨識引擎", self.menu)
        
        self.action_engine_win = QAction("Windows 內建 OCR (推薦、速度快)", self.menu, checkable=True)
        self.action_engine_tes = QAction("Tesseract OCR (傳統)", self.menu, checkable=True)
        
        # 根據設定打勾
        if self.ocr_engine == 'tesseract':
            self.action_engine_tes.setChecked(True)
        else:
            self.action_engine_win.setChecked(True)
            
        self.action_engine_win.triggered.connect(lambda: self.set_ocr_engine('windows'))
        self.action_engine_tes.triggered.connect(lambda: self.set_ocr_engine('tesseract'))
        
        self.menu_engine.addAction(self.action_engine_win)
        self.menu_engine.addAction(self.action_engine_tes)
        
        self.action_quit = QAction("退出程式")
        self.action_quit.triggered.connect(self.quit_app)

        # 翻譯引擎選擇 (次選單)
        self.menu_translator = QMenu("翻譯引擎", self.menu)

        self.action_trans_google = QAction(
            "Google 翻譯（免費、無需 Key）", self.menu, checkable=True)
        self.action_trans_bing = QAction(
            "Bing 翻譯（免費、無需 Key）", self.menu, checkable=True)

        if self.translator_engine == 'bing':
            self.action_trans_bing.setChecked(True)
        else:
            self.action_trans_google.setChecked(True)

        self.action_trans_google.triggered.connect(lambda: self.set_translator_engine('google'))
        self.action_trans_bing.triggered.connect(lambda: self.set_translator_engine('bing'))

        self.menu_translator.addAction(self.action_trans_google)
        self.menu_translator.addAction(self.action_trans_bing)
        
        self.menu.addAction(self.action_version)
        self.menu.addAction(self.action_update)
        self.menu.addSeparator()
        self.menu.addAction(self.action_translate)
        self.menu.addAction(self.action_font)
        self.menu.addMenu(self.menu_engine)
        self.menu.addMenu(self.menu_translator)
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
            self.selection_window.hide()
            self.selection_window.close()
            self.selection_window.deleteLater()
            self.selection_window = None
            
        if self.result_window:
            self.result_window.hide()
            self.result_window.close()
            self.result_window.deleteLater()
            self.result_window = None
            
        if self.loading_window:
            self.loading_window.hide()
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
        if self.selection_window:
            self.selection_window.hide()
            self.selection_window.close()
            self.selection_window.deleteLater()
            self.selection_window = None

    def on_selection_completed(self, rect):
        """
        使用者完成選取後觸發，啟用 QThread 背景翻譯，並改變滑鼠游標狀態以提示載入中。
        """
        self.target_rect = rect
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        # 1. 立即先抓取螢幕畫面，確保不會抓到後續顯示的「辨識中...」視窗
        x, y = rect.x(), rect.y()
        w, h = rect.width(), rect.height()
        temp_img_path = capture_screen(x, y, w, h)
        
        # 顯示「辨識中...」
        if self.loading_window:
            self.loading_window.hide()
            self.loading_window.close()
            self.loading_window.deleteLater()
            self.loading_window = None
            
        self.loading_window = LoadingOverlayWindow(rect)
        self.loading_window.show()
        
        self.worker = TranslationWorker(
            rect,
            font_path=self.font_path,
            font_family=self.font_family,
            ocr_engine=self.ocr_engine,
            translator_engine=self.translator_engine,
            img_path=temp_img_path
        )
        self.worker.finished.connect(self.on_translation_finished)
        self.worker.error.connect(self.on_translation_error)
        self.worker.start()

    def set_ocr_engine(self, engine: str):
        """切換 OCR 引擎並儲存設定"""
        self.ocr_engine = engine
        self._cfg['ocr_engine'] = engine
        cfg_module.save_config(self._cfg)
        
        # UI 單選互斥處理
        if engine == 'windows':
            self.action_engine_win.setChecked(True)
            self.action_engine_tes.setChecked(False)
            self.tray_icon.showMessage("引擎切換", "已切換為：Windows 內建 OCR", QSystemTrayIcon.Information, 2000)
        else:
            self.action_engine_win.setChecked(False)
            self.action_engine_tes.setChecked(True)
            self.tray_icon.showMessage("引擎切換", "已切換為：Tesseract OCR", QSystemTrayIcon.Information, 2000)

    def set_translator_engine(self, engine: str):
        """切換翻譯引擎並儲存設定"""
        self.translator_engine = engine
        self._cfg['translator_engine'] = engine
        cfg_module.save_config(self._cfg)

        if engine == 'bing':
            self.action_trans_google.setChecked(False)
            self.action_trans_bing.setChecked(True)
            self.tray_icon.showMessage("翻譯引擎", "已切換為：Bing 翻譯（免費）",
                                       QSystemTrayIcon.Information, 2000)
        else:
            self.action_trans_google.setChecked(True)
            self.action_trans_bing.setChecked(False)
            self.tray_icon.showMessage("翻譯引擎", "已切換為：Google 翻譯",
                                       QSystemTrayIcon.Information, 2000)

    def open_font_settings(self):
        """開啟字體選擇對話框，儲存至 config.json"""
        self._show_custom_font_dialog()

    def _show_custom_font_dialog(self):
        """自定義的字型選擇對話框，只顯示字型家族，不顯示大小與粗細"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFontComboBox, QLabel, QFrame
        
        dlg = QDialog()
        dlg.setWindowTitle("選擇翻譯字體")
        dlg.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.WindowContextHelpButtonHint)
        dlg.setFixedSize(380, 200)
        
        # 套用現代化樣式表
        dlg.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QLabel {
                font-size: 14px;
                color: #333333;
            }
            QLabel#hintLabel {
                font-size: 12px;
                color: #666666;
            }
            QFontComboBox {
                font-size: 14px;
                padding: 6px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
            }
            QFontComboBox::drop-down {
                border-left: 1px solid #ced4da;
                width: 30px;
            }
            QPushButton {
                font-size: 14px;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton#okBtn {
                background-color: #0d6efd;
                color: white;
                border: none;
            }
            QPushButton#okBtn:hover {
                background-color: #0b5ed7;
            }
            QPushButton#cancelBtn {
                background-color: white;
                color: #333333;
                border: 1px solid #ced4da;
            }
            QPushButton#cancelBtn:hover {
                background-color: #e9ecef;
            }
        """)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)
        
        # 標題區
        title_label = QLabel("選擇您偏好的翻譯顯示字體：")
        title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        main_layout.addWidget(title_label)
        
        # 字體下拉選單
        font_combo = QFontComboBox()
        current_family = self._cfg.get('font_family', '')
        if current_family:
            font_combo.setCurrentFont(QFont(current_family))
        main_layout.addWidget(font_combo)
        
        # 溫馨提示
        hint_label = QLabel("💡 字體大小與粗細會由系統自動依照來源圖片版面計算，\n為保持最佳排版效果，此處僅需選擇字型款式。")
        hint_label.setObjectName("hintLabel")
        main_layout.addWidget(hint_label)
        
        main_layout.addStretch()
        
        # 按鈕區
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        
        ok_btn = QPushButton("儲存設定")
        ok_btn.setObjectName("okBtn")
        ok_btn.setCursor(Qt.PointingHandCursor)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        
        main_layout.addLayout(btn_layout)
        dlg.setLayout(main_layout)
        
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        
        if dlg.exec_() == QDialog.Accepted:
            font = font_combo.currentFont()
            family = font.family()
            path = cfg_module.find_font_path(family)
            
            self._cfg['font_family'] = family
            self._cfg['font_path'] = path
            self.font_path = path
            self.font_family = family
            cfg_module.save_config(self._cfg)
            
            display = f"字體已設為：{family}"
            if not path:
                display += "\n（⚠️ 找不到對應的字型檔，將退回使用預設字體）"
            self.tray_icon.showMessage("字體設定成功", display, QSystemTrayIcon.Information, 3000)

    def on_translation_finished(self, out_img_path):
        """
        當背景翻譯與影像處理成功後觸發，顯示翻譯好的圖片
        """
        QApplication.restoreOverrideCursor()
        
        # 關閉載入提示
        if self.loading_window:
            self.loading_window.hide()
            self.loading_window.close()
            self.loading_window.deleteLater()
            self.loading_window = None
        
        if not self.result_window:
            self.result_window = ImageOverlayWindow()
            
        self.result_window.set_image(out_img_path, self.target_rect)
        
        if self.selection_window:
            self.selection_window.hide()
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
            self.loading_window.hide()
            self.loading_window.close()
            self.loading_window.deleteLater()
            self.loading_window = None
            
        QMessageBox.warning(None, "發生錯誤", error_msg)
        
        if self.selection_window:
            self.selection_window.hide()
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
    
    # 確保終端機按下 Ctrl+C 時能被 Python 擷取並退出
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    # 3. 執行主程式核心邏輯
    snap_app = SnapTransApp()
    snap_app.run()
    
    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        snap_app.quit_app()
