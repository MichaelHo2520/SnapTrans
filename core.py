import sys
import mss
import mss.tools
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import re
import string
import statistics
import requests
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

def _is_cjk(ch):
    """判斷字元是否屬於 CJK 漢字或全形標點範圍"""
    return '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef'


_bing_token_cache: dict = {}   # {'token': str, 'expires': float}


def _get_bing_token() -> str:
    """
    從 Edge 瀏覽器的翻譯服務取得免費的 Bearer Token（無需 API Key）。
    Token 有效期約 10 分鐘，使用模組層級快取避免頻繁請求。
    """
    import time
    now = time.time()
    if _bing_token_cache.get('token') and now < _bing_token_cache.get('expires', 0):
        return _bing_token_cache['token']

    resp = requests.get('https://edge.microsoft.com/translate/auth', timeout=10)
    resp.raise_for_status()
    token = resp.text.strip()
    _bing_token_cache['token'] = token
    _bing_token_cache['expires'] = now + 540   # 快取 9 分鐘 (保守估計)
    return token


def _translate(text: str, engine: str = 'google') -> str:
    """
    統一翻譯入口。engine: 'google' | 'bing'
    """
    if not text or not text.strip():
        return text

    # ---- Bing 翻譯（免費，無需 Key，透過 Edge 內建 Token）----
    if engine == 'bing':
        try:
            token = _get_bing_token()
            url = 'https://api.cognitive.microsofttranslator.com/translate'
            params  = {'api-version': '3.0', 'to': 'zh-Hant'}
            headers = {'Authorization': f'Bearer {token}',
                       'Content-Type':  'application/json'}
            resp = requests.post(url, params=params, headers=headers,
                                 json=[{'text': text}], timeout=10)
            resp.raise_for_status()
            return resp.json()[0]['translations'][0]['text']
        except Exception:
            pass   # 失敗時 fallback 至 Google

    # ---- Google Translator（預設 / fallback）----
    try:
        return GoogleTranslator(source='auto', target='zh-TW').translate(text)
    except Exception:
        return text


def process_and_translate_image(image_path, font_path=None, font_family=None,
                                ocr_engine='tesseract',
                                translator_engine='google'):
    """
    讀取圖片、進行 OCR 定位、翻譯文字，並將翻譯結果直接繪製(覆蓋)回圖片上。
    font_path:         使用者指定的字型檔路徑（None 表示自動選擇）
    font_family:       使用者指定的字型名稱
    ocr_engine:        'tesseract' 或 'windows'
    translator_engine: 'google' 或 'bing'
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
            
            # 修正間距判斷邏輯：如果間隔大於平均字寬 1.5 倍或 12px，視為獨立區塊
            # (降低原先 20px 的硬限制，避免小字體的選單列如 File Edit 被合併成一整行)
            if gap > max(avg_char_w * 1.5, 12):
                final_groups.append(group)
                group = [curr]
            else:
                group.append(curr)
        final_groups.append(group)   # 必須在 for words 迴圈內，每條 line 結束後都要 append
    
    # 3. 計算統一字體大小（以所有群組行高的中位數為基準，避免字大小不一）
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
        
        # 智慧字串組合：
        # - 中英文 / 英中 之間加空白
        # - 純英文 token 之間加空白
        # - 兩個相鄰中文 token 之間若有「大間距」（可能是被過濾掉的標點），也加空白

        # 預先算出本群組的平均字元寬（用來判斷「明顯間距」）
        grp_total_chars = sum(len(x['text']) for x in group)
        grp_total_width = sum(x['width'] for x in group)
        grp_avg_char_w  = grp_total_width / grp_total_chars if grp_total_chars > 0 else 14

        eng_text = ""
        for wi, w in enumerate(group):
            t = w['text']
            if not eng_text:
                eng_text = t
            else:
                prev_w   = group[wi - 1]
                pixel_gap = w['left'] - (prev_w['left'] + prev_w['width'])

                last_char  = eng_text[-1]
                first_char = t[0]
                last_is_cjk  = _is_cjk(last_char)
                first_is_cjk = _is_cjk(first_char)

                if last_is_cjk and first_is_cjk:
                    # 兩邊都是中文：只有在間距明顯偏大時才插空白（表示中文標點被過濾掉了）
                    if pixel_gap > grp_avg_char_w * 0.8:
                        eng_text += " " + t
                    else:
                        eng_text += t
                else:
                    # 只要有一個是英文/數字/ASCII，就加上空白
                    eng_text += " " + t
        zh_text = _translate(eng_text, translator_engine)
        
        # 蓋掉原文 (使用更大的 padding 來確保原始文字的邊角完全被覆蓋)
        draw.rectangle((p_left, p_top, p_right, p_bottom), fill=bg_color)
        
        # 使用統一字體，垂直置中
        box_height = bottom - top
        y_offset   = max(0, (box_height - unified_font_size) // 2)
        draw.text((left, top + y_offset), zh_text, font=unified_font, fill=fg_color)
    
    out_path = image_path.replace(".png", "_translated.png")
    img.save(out_path)
    return out_path, None

