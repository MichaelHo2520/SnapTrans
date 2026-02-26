import sys
import mss
import mss.tools
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import re
from deep_translator import GoogleTranslator
import os

# 設定 Tesseract 的執行路徑 (優先使用打包附帶的可攜版)
# PyInstaller 打包後，檔案會解壓縮到 sys._MEIPASS 或在同層目錄
if hasattr(sys, '_MEIPASS'):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

bundled_tesseract = os.path.join(base_dir, "Tesseract-OCR", "tesseract.exe")
if os.path.exists(bundled_tesseract):
    pytesseract.pytesseract.tesseract_cmd = bundled_tesseract
else:
    # 預設嘗試系統環境變數
    pass

def capture_screen(x, y, width, height, output_filename="temp_capture.png"):
    """
    擷取指定座標範圍的螢幕畫面並儲存為圖片檔
    """
    temp_dir = os.path.join(base_dir, "temp")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
        
    out_path = os.path.join(temp_dir, output_filename)
        
    with mss.mss() as sct:
        monitor = {"top": y, "left": x, "width": width, "height": height}
        sct_img = sct.grab(monitor)
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=out_path)
        return out_path

def get_chinese_font(size):
    """嘗試載入支援中文的字體"""
    font_names = ["msjh.ttc", "simhei.ttf", "mingliu.ttc", "arial.ttf"]
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()

def process_and_translate_image(image_path):
    """
    讀取圖片、進行 OCR 定位、翻譯文字，並將翻譯結果直接繪製(覆蓋)回圖片上。
    """
    try:
        img = Image.open(image_path).convert('RGB')
    except Exception as e:
        return None, f"無法開啟圖片: {e}"
        
    draw = ImageDraw.Draw(img)
    
    try:
        # 使用 image_to_data 獲取詳細的座標資訊
        data = pytesseract.image_to_data(img, lang='eng', output_type=pytesseract.Output.DICT)
    except Exception as e:
        return None, f"OCR 辨識發生錯誤: {e}"
        
    # 1. 將讀取到的單字組合成行 (Block + Line)
    lines = {}
    for i in range(len(data['text'])):
        conf = int(data['conf'][i])
        text = data['text'][i].strip()
        
        # 過濾低信心度與空字串
        if conf > 30 and text:
            # 簡單過濾掉純雜訊 (必須包含至少一個英文字母或數字)
            if re.search(r'[a-zA-Z0-9]', text):
                block_line = f"{data['block_num'][i]}_{data['line_num'][i]}"
                if block_line not in lines:
                    lines[block_line] = {'words': [], 'left': [], 'top': [], 'width': [], 'height': []}
                
                lines[block_line]['words'].append(text)
                lines[block_line]['left'].append(data['left'][i])
                lines[block_line]['top'].append(data['top'][i])
                lines[block_line]['width'].append(data['width'][i])
                lines[block_line]['height'].append(data['height'][i])

    if not lines:
        return None, "未能辨識出任何有效文字，請重新選取。"

    translator = GoogleTranslator(source='en', target='zh-TW')
    
    # 2. 處理每一行文字，翻譯並覆蓋回原圖
    for key, line_data in lines.items():
        # 計算這一整行的邊界框
        left = min(line_data['left'])
        top = min(line_data['top'])
        right = max([l + w for l, w in zip(line_data['left'], line_data['width'])])
        bottom = max([t + h for t, h in zip(line_data['top'], line_data['height'])])
        
        # 為了取樣背景色，將邊界稍微往外擴展一點
        p_left = max(0, left - 2)
        p_top = max(0, top - 2)
        p_right = min(img.width, right + 2)
        p_bottom = min(img.height, bottom + 2)
        
        box_img = img.crop((p_left, p_top, p_right, p_bottom))
        colors = box_img.getcolors(maxcolors=100000)
        
        if not colors:
            continue
            
        colors.sort(reverse=True)
        # 最常出現的顏色當作背景色
        bg_color = colors[0][1] 
        
        # 根據背景亮度決定使用反白或反黑的字體顏色
        luminance = 0.299*bg_color[0] + 0.587*bg_color[1] + 0.114*bg_color[2]
        if luminance < 128:
            # 深色背景 -> 找最亮的顏色當前景色
            fg_color = max([c[1] for c in colors], key=lambda x: 0.299*x[0] + 0.587*x[1] + 0.114*x[2])
            # 防呆：如果找到的還是不夠亮，強制用白色
            if abs(luminance - (0.299*fg_color[0] + 0.587*fg_color[1] + 0.114*fg_color[2])) < 50:
                fg_color = (255, 255, 255)
        else:
            # 淺色背景 -> 找最暗的顏色當前景色
            fg_color = min([c[1] for c in colors], key=lambda x: 0.299*x[0] + 0.587*x[1] + 0.114*x[2])
            if abs(luminance - (0.299*fg_color[0] + 0.587*fg_color[1] + 0.114*fg_color[2])) < 50:
                fg_color = (0, 0, 0)
                
        # 原始英文
        eng_text = " ".join(line_data['words'])
        
        # 翻譯
        try:
            zh_text = translator.translate(eng_text)
        except Exception:
            zh_text = eng_text # 翻譯失敗則保留原文
            
        # 畫背景色塊蓋掉原本的字
        # 為了避免蓋到隔壁的字，只填滿精確的 bounding box
        exp_left = max(0, left - 1)
        exp_top = max(0, top - 1)
        exp_right = min(img.width, right + 1)
        exp_bottom = min(img.height, bottom + 1)
        draw.rectangle((exp_left, exp_top, exp_right, exp_bottom), fill=bg_color)
        
        # 繪製翻譯結果
        box_height = bottom - top
        font_size = max(12, int(box_height * 0.85)) # 動態字體大小
        font = get_chinese_font(font_size)
        
        # 稍微往下偏移一點點讓文字置中
        y_offset = max(0, int(box_height * 0.05))
        draw.text((left, top + y_offset), zh_text, font=font, fill=fg_color)
        
    out_path = image_path.replace(".png", "_translated.png")
    img.save(out_path)
    return out_path, None
