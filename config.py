import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

DEFAULT_CONFIG = {
    'font_family':       '',         # 空字串 = 自動選擇
    'font_path':         '',         # 字型檔完整路徑
    'ocr_engine':        'windows',  # 'windows' | 'tesseract'
    'translator_engine': 'google',   # 'google'  | 'bing'
    'autostart':         False,      # 開機自動啟動
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return {**DEFAULT_CONFIG, **cfg}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def find_font_path(family_name: str) -> str:
    """
    使用 QFontDatabase 查詢字型家族對應的字型檔案。
    QFontDatabase 會處理不同語言的字型名稱映射 (例如將 '標楷體' 映射到 DFKai-SB/kaiu.ttf)。
    """
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QFontDatabase, QFont, QFontInfo
        
        internal_family = ""
        # QApplication 必須存在才能使用 QFontDatabase
        if QApplication.instance():
            db = QFontDatabase()
            if family_name in db.families():
                font = QFont(family_name)
                fontInfo = QFontInfo(font)
                internal_family = fontInfo.family()
        
        # 嘗試從 registry 拿，因為 QFontDatabase 有時候還是沒有直接給 path 的 API
        import winreg
        fonts_dir = r"C:\Windows\Fonts"
        reg_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)

        # 建立常見中文字型名稱映射表（UI 顯示名稱 -> Registry 內部名稱片段）
        # 因為 Windows Registry 裡通常存的是英文或特定的內部名稱
        font_name_map = {
            '標楷體': 'kai',
            '微軟正黑體': 'jhenghei',
            '新細明體': 'mingliu',
            '細明體': 'mingliu',
            '微軟雅黑': 'yahei',
            '黑體': 'simhei',
            '宋體': 'simsun',
            '仿宋': 'fangsong',
            '楷體': 'kaiti',
        }
        
        target1 = family_name.lower().replace(' ', '')
        target2 = internal_family.lower().replace(' ', '') if internal_family else ''
        target3 = font_name_map.get(family_name, '').lower()

        best = ''
        i = 0
        while True:
            try:
                reg_name, reg_value, _ = winreg.EnumValue(key, i)
                i += 1
                display = reg_name.split('(')[0].strip().lower().replace(' ', '')
                if (display == target1 or (target2 and display == target2) or 
                    (target3 and target3 in display) or
                    display.startswith(target1) or (target2 and display.startswith(target2))):
                    fpath = reg_value if os.path.isabs(reg_value) \
                            else os.path.join(fonts_dir, reg_value)
                    if not best:
                        best = fpath
                    # 優先 Regular
                    low = reg_name.lower()
                    if 'bold' not in low and 'italic' not in low:
                        best = fpath
            except OSError:
                break
        winreg.CloseKey(key)
        return best
    except Exception:
        return ''
