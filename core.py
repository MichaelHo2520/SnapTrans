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

def get_chinese_font(size, preferred_path=None, family_name=None):
    """嘗試載入支援中文的字體；優先使用使用者指定的字型"""
    # 策略 1: 優先嘗試絕對路徑
    if preferred_path:
        try:
            return ImageFont.truetype(preferred_path, size)
        except OSError:
            pass
            
    # 策略 2: 嘗試用內建的名稱映射去找字型 (PIL ImageFont 有時能直接依檔名找到)
    if family_name:
        font_name_map = {
            '標楷體': 'kaiu.ttf',
            '微軟正黑體': 'msjh.ttc',
            '新細明體': 'mingliu.ttc',
            '細明體': 'mingliu.ttc',
            '微軟雅黑': 'msyh.ttc',
            '黑體': 'simhei.ttf',
            '宋體': 'simsun.ttc',
            '仿宋': 'simfang.ttf',
            '楷體': 'simkai.ttf',
        }
        mapped_name = font_name_map.get(family_name)
        if mapped_name:
            try:
                return ImageFont.truetype(mapped_name, size)
            except OSError:
                pass
                
        # 也有可能 PIL 可以直接解析該名稱字串
        try:
            return ImageFont.truetype(family_name, size)
        except OSError:
            pass

    # 策略 3: fallback 備用字體清單
    font_names = ["msjh.ttc", "simhei.ttf", "mingliu.ttc", "arial.ttf"]
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()

def process_and_translate_image(image_path, font_path=None, font_family=None):
    """
    讀取圖片、進行 OCR 定位、翻譯文字，並將翻譯結果直接繪製(覆蓋)回圖片上。
    改進：以水平間距做二次分組，避免同行不同段落被合為一組。
    font_path: 使用者指定的字型檔路徑（None 表示自動選擇）
    font_family: 使用者指定的字型名稱
    """
    try:
        img = Image.open(image_path).convert('RGB')
    except Exception as e:
        return None, f"無法開啟圖片: {e}"
        
    draw = ImageDraw.Draw(img)
    
    try:
        data = pytesseract.image_to_data(img, lang='eng+chi_tra', output_type=pytesseract.Output.DICT)
    except Exception as e:
        return None, f"OCR 辨識發生錯誤: {e}"
    
    # 1. 收集有效單字（過濾低信心、空字串、純雜訊、單一字元圖示誤判）
    valid_words = []
    for i in range(len(data['text'])):
        conf = int(data['conf'][i])
        text = data['text'][i].strip()
        # 放寬條件：只要有英文字母、數字或中文字元，且信心度夠高就納入
        if conf > 30 and text and re.search(r'[a-zA-Z0-9\u4e00-\u9fff]', text):
            valid_words.append({
                'text':     text,
                'left':     data['left'][i],
                'top':      data['top'][i],
                'width':    data['width'][i],
                'height':   data['height'][i],
                'block':    data['block_num'][i],
                'line':     data['line_num'][i],
            })
    
    if not valid_words:
        return None, "未能辨識出任何有效文字，請重新選取。"
    
    # 2. 先按 block+line 合成粗分組，再依水平間距做細分
    line_buckets = {}
    for w in valid_words:
        key = (w['block'], w['line'])
        line_buckets.setdefault(key, []).append(w)
    
    final_groups = []
    for words in line_buckets.values():
        words.sort(key=lambda w: w['left'])
        group = [words[0]]
        for i in range(1, len(words)):
            prev = group[-1]
            curr = words[i]
            gap = curr['left'] - (prev['left'] + prev['width'])
            avg_w = sum(x['width'] for x in group) / len(group)
            # 間距超過平均字寬 1.5 倍或 30px 就視為新段落
            if gap > max(avg_w * 1.5, 30):
                final_groups.append(group)
                group = [curr]
            else:
                group.append(curr)
        final_groups.append(group)
    
    translator = GoogleTranslator(source='auto', target='zh-TW')
    
    # 3. 計算統一字體大小（以所有群組行高的中位數為基準，避免字大小不一）
    import statistics
    all_heights = []
    for group in final_groups:
        h = max(w['top'] + w['height'] for w in group) - min(w['top'] for w in group)
        all_heights.append(h)
    median_height = statistics.median(all_heights) if all_heights else 20
    unified_font_size = max(12, int(median_height * 0.85))
    unified_font = get_chinese_font(unified_font_size, preferred_path=font_path, family_name=font_family)

    # 4. 對每個群組翻譯並覆蓋回原圖
    for group in final_groups:
        left   = min(w['left'] for w in group)
        top    = min(w['top']  for w in group)
        right  = max(w['left'] + w['width']  for w in group)
        bottom = max(w['top']  + w['height'] for w in group)
        
        # 取樣背景色
        p_left   = max(0, left   - 2)
        p_top    = max(0, top    - 2)
        p_right  = min(img.width,  right  + 2)
        p_bottom = min(img.height, bottom + 2)
        
        box_img = img.crop((p_left, p_top, p_right, p_bottom))
        colors  = box_img.getcolors(maxcolors=100000)
        if not colors:
            continue
        colors.sort(reverse=True)
        bg_color  = colors[0][1]
        luminance = 0.299*bg_color[0] + 0.587*bg_color[1] + 0.114*bg_color[2]
        
        if luminance < 128:
            fg_color = max([c[1] for c in colors], key=lambda x: 0.299*x[0] + 0.587*x[1] + 0.114*x[2])
            if abs(luminance - (0.299*fg_color[0] + 0.587*fg_color[1] + 0.114*fg_color[2])) < 50:
                fg_color = (255, 255, 255)
        else:
            fg_color = min([c[1] for c in colors], key=lambda x: 0.299*x[0] + 0.587*x[1] + 0.114*x[2])
            if abs(luminance - (0.299*fg_color[0] + 0.587*fg_color[1] + 0.114*fg_color[2])) < 50:
                fg_color = (0, 0, 0)
        
        eng_text = " ".join(w['text'] for w in group)
        try:
            zh_text = translator.translate(eng_text)
        except Exception:
            zh_text = eng_text
        
        # 蓋掉原文
        draw.rectangle((max(0, left-1), max(0, top-1),
                         min(img.width, right+1), min(img.height, bottom+1)),
                        fill=bg_color)
        
        # 使用統一字體，垂直置中
        box_height = bottom - top
        y_offset   = max(0, (box_height - unified_font_size) // 2)
        draw.text((left, top + y_offset), zh_text, font=unified_font, fill=fg_color)
    
    out_path = image_path.replace(".png", "_translated.png")
    img.save(out_path)
    return out_path, None

