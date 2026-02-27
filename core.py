import sys
import mss
import mss.tools
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import re
from deep_translator import GoogleTranslator
import os
import asyncio

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

def process_and_translate_image(image_path, font_path=None, font_family=None, ocr_engine='tesseract'):
    """
    讀取圖片、進行 OCR 定位、翻譯文字，並將翻譯結果直接繪製(覆蓋)回圖片上。
    改進：以水平間距做二次分組，避免同行不同段落被合為一組。
    font_path: 使用者指定的字型檔路徑（None 表示自動選擇）
    font_family: 使用者指定的字型名稱
    ocr_engine: 'tesseract' 或 'windows'
    """
    try:
        img = Image.open(image_path).convert('RGB')
    except Exception as e:
        return None, f"無法開啟圖片: {e}"
        
    draw = ImageDraw.Draw(img)
    
    # 1. 收集有效單字（過濾低信心、空字串、純雜訊、單一字元圖示誤判）
    valid_words = []
    
    if ocr_engine == 'windows':
        # 使用 Windows 內建 OCR
        try:
            from winsdk.windows.media.ocr import OcrEngine
            from winsdk.windows.graphics.imaging import BitmapDecoder
            from winsdk.windows.storage import StorageFile
            import winsdk.windows.globalization as gl

            # 針對小字體進行 3 倍放大，顯著提升 Windows OCR 在小字、編輯器字體上的辨識率
            OCR_SCALE = 3.0
            upscaled_size = (int(img.width * OCR_SCALE), int(img.height * OCR_SCALE))
            upscaled_img = img.resize(upscaled_size, Image.Resampling.LANCZOS)
            
            temp_dir = os.path.join(base_dir, "temp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir, exist_ok=True)
            temp_ocr_path = os.path.join(temp_dir, "temp_ocr_upscaled.png")
            upscaled_img.save(temp_ocr_path)

            async def do_win_ocr(file_path):
                file = await StorageFile.get_file_from_path_async(os.path.abspath(file_path))
                stream = await file.open_async(0) # FileAccessMode.Read = 0
                decoder = await BitmapDecoder.create_async(stream)
                bitmap = await decoder.get_software_bitmap_async()
                engine = OcrEngine.try_create_from_user_profile_languages()
                result = await engine.recognize_async(bitmap)
                return result

            # 若當前事件循環已在運行 (例如在 PyQt 的某些情境)，建立新 loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            win_ocr_result = loop.run_until_complete(do_win_ocr(temp_ocr_path))
            loop.close()

            # 解析 Windows OCR 結果
            line_idx = 0
            for line in win_ocr_result.lines:
                for word in line.words:
                    text_str = word.text.strip()
                    
                    # 1. 基礎過濾：必須包含字母、數字或漢字
                    if not text_str or not re.search(r'[a-zA-Z0-9\u4e00-\u9fff]', text_str):
                        continue
                        
                    # 把放大後的座標縮回原本圖片的比例
                    rect = word.bounding_rect
                    orig_x = rect.x / OCR_SCALE
                    orig_y = rect.y / OCR_SCALE
                    orig_w = rect.width / OCR_SCALE
                    orig_h = rect.height / OCR_SCALE

                    # 2. 圖示雜訊過濾：防呆檢查異常的文字框尺寸 (通常小圖示會被誤認為極細或極小的字)
                    if orig_w <= 2 or orig_h <= 2:
                        continue
                        
                    # 若為單一非漢字字元，檢查是否為常見圖示誤判 (例如單一的 O, l, I 且寬高比過大/過小)
                    is_chinese_char = bool(re.search(r'[\u4e00-\u9fff]', text_str))
                    aspect_ratio = orig_w / orig_h if orig_h > 0 else 1
                    if len(text_str) == 1 and not is_chinese_char:
                        if aspect_ratio < 0.2 or aspect_ratio > 5.0:
                            continue
                            
                    # 3. 亂碼雜訊過濾：
                    # a. 計算有效字元比例
                    valid_char_count = len(re.findall(r'[a-zA-Z0-9\u4e00-\u9fff]', text_str))
                    if valid_char_count / len(text_str) < 0.4:
                        continue
                        
                    # b. 進階雜湊過濾 (專門針對如條狀圖、血條等被誤認成文字：例如 l-E+PAE8)
                    # 特徵：包含加號、等號、減號，並且周遭都是大寫字母或數字，且沒有正常單字的結構
                    if re.search(r'[+\-=>\|_~]', text_str) and not is_chinese_char:
                        # 計算符號佔比
                        symbol_ratio = len(re.findall(r'[^a-zA-Z0-9\s]', text_str)) / len(text_str)
                        if symbol_ratio > 0.2 and len(text_str) <= 10:
                            # 很可能是血條或分隔線雜訊
                            continue
                    
                    valid_words.append({
                        'text': text_str,
                        'left': orig_x,
                        'top': orig_y,
                        'width': orig_w,
                        'height': orig_h,
                        'block': 1, # Win OCR 沒有 block 概念，全部放同一個 block
                        'line': line_idx
                    })
                line_idx += 1
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None, f"Windows OCR 辨識發生錯誤: {e}"
            
    else: # 預設 tesseract
        try:
            data = pytesseract.image_to_data(img, lang='eng+chi_tra', output_type=pytesseract.Output.DICT)
        except Exception as e:
            return None, f"Tesseract OCR 辨識發生錯誤: {e}"
            
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
            
            # 使用平均「字元」寬度來判斷間距 (避免欄位選單整行被合併)
            total_chars = sum(len(x['text']) for x in group)
            total_width = sum(x['width'] for x in group)
            avg_char_w = total_width / total_chars if total_chars > 0 else 10
            
            # 放寬間距到平均字寬 2.5 倍或 20px 確保中文全形標點不會被斷開
            if gap > max(avg_char_w * 2.5, 20):
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
        
        # 取樣背景色 (範圍稍微往外擴大，避免邊緣取到太多文字顏色，也為之後覆蓋做準備)
        padding = 4
        p_left   = max(0, left   - padding)
        p_top    = max(0, top    - padding)
        p_right  = min(img.width,  right  + padding)
        p_bottom = min(img.height, bottom + padding)
        
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
        
        # 智慧字串組合：中文字之間不加空白，中英文之間或單純英文之間才加空白
        import string
        eng_text = ""
        for w in group:
            t = w['text']
            if not eng_text:
                eng_text = t
            else:
                last_char = eng_text[-1]
                first_char = t[0]
                # 判斷是否為「非」中日韓文字 (即英文或數字)
                last_is_ascii = last_char in string.ascii_letters or last_char in string.digits or last_char in string.punctuation
                first_is_ascii = first_char in string.ascii_letters or first_char in string.digits or first_char in string.punctuation
                
                # 如果前一個字和後一個字都是中文字，就不加空白
                if not last_is_ascii and not first_is_ascii:
                    eng_text += t
                else:
                    # 只要有一個是英文/數字，就加上空白
                    eng_text += " " + t
        try:
            zh_text = translator.translate(eng_text)
        except Exception:
            zh_text = eng_text
        
        # 蓋掉原文 (使用更大的 padding 來確保原始文字的邊角完全被覆蓋)
        draw.rectangle((p_left, p_top, p_right, p_bottom), fill=bg_color)
        
        # 使用統一字體，垂直置中
        box_height = bottom - top
        y_offset   = max(0, (box_height - unified_font_size) // 2)
        draw.text((left, top + y_offset), zh_text, font=unified_font, fill=fg_color)
    
    out_path = image_path.replace(".png", "_translated.png")
    img.save(out_path)
    return out_path, None

