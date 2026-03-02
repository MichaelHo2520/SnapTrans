import os
from PIL import Image, ImageDraw, ImageFont
import asyncio
from core import get_chinese_font, process_and_translate_image

# 1. 產生測試圖片
def generate_test_image(filename, text_lines, bg_color=(40, 40, 40), fg_color=(255, 255, 255)):
    img = Image.new('RGB', (800, 400), color=bg_color)
    draw = ImageDraw.Draw(img)
    font = get_chinese_font(32)
    
    y = 50
    for line in text_lines:
        draw.text((50, y), line, font=font, fill=fg_color)
        y += 60
        
    # 畫幾個干擾的小圖示 (例如 2x2 或極細長的長條)
    draw.rectangle([50, y, 60, y+2], fill=(200, 50, 50)) # 扁平血條雜訊
    draw.rectangle([100, y, 102, y+15], fill=(50, 200, 50)) # 細長游標雜訊
        
    img.save(filename)
    return filename

if __name__ == '__main__':
    if not os.path.exists("test_cases"):
        os.makedirs("test_cases")
        
    import glob
    test_files = glob.glob(os.path.join("test_cases", "*.png"))
    
    if not test_files:
        print(f"錯誤：找不到測試圖片")
        sys.exit(1)
        
    import re
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage import StorageFile

    async def run_win_ocr(file_path):
        print(f"\n--- 開始測試 Windows OCR 解析結果 ({file_path}) ---")
        file = await StorageFile.get_file_from_path_async(os.path.abspath(file_path))
        stream = await file.open_async(0)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        engine = OcrEngine.try_create_from_user_profile_languages()
        result = await engine.recognize_async(bitmap)
        
        valid_words = []
        line_idx = 0
        for line in result.lines:
            for word in line.words:
                text_str = word.text.strip()
                if not text_str or not re.search(r'[a-zA-Z0-9\u4e00-\u9fff]', text_str):
                    continue
                rect = word.bounding_rect
                if rect.width <= 2 or rect.height <= 2:
                    continue
                is_chinese_char = bool(re.search(r'[\u4e00-\u9fff]', text_str))
                aspect_ratio = rect.width / rect.height
                if len(text_str) == 1 and not is_chinese_char:
                    if aspect_ratio < 0.2 or aspect_ratio > 5.0:
                        continue
                        
                # a. 計算有效字元比例
                valid_char_count = len(re.findall(r'[a-zA-Z0-9\u4e00-\u9fff]', text_str))
                if valid_char_count / len(text_str) < 0.4:
                    continue
                    
                # b. 進階雜湊過濾 (專門針對如條狀圖、血條等被誤認成文字：例如 l-E+PAE8)
                if re.search(r'[+\-=>\|_~]', text_str) and not is_chinese_char:
                    symbol_ratio = len(re.findall(r'[^a-zA-Z0-9\s]', text_str)) / len(text_str)
                    if symbol_ratio > 0.2 and len(text_str) <= 10:
                        continue
                
                valid_words.append({
                    'text': text_str,
                    'left': rect.x,
                    'width': rect.width,
                    'block': 1,
                    'line': line_idx
                })
            line_idx += 1
            
        # 群組與組合邏輯 (複製自 core.py)
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
                
                total_chars = sum(len(x['text']) for x in group)
                total_width = sum(x['width'] for x in group)
                avg_char_w = total_width / total_chars if total_chars > 0 else 10
                
                if gap > max(avg_char_w * 1.5, 12):
                    final_groups.append(group)
                    group = [curr]
                else:
                    group.append(curr)
            final_groups.append(group)
            
        # 顯示結果
        import string

        def _is_cjk(ch):
            return '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef'

        for group in final_groups:
            grp_total_chars = sum(len(x['text']) for x in group)
            grp_total_width = sum(x['width'] for x in group)
            grp_avg_char_w  = grp_total_width / grp_total_chars if grp_total_chars > 0 else 14

            eng_text = ""
            for wi, w in enumerate(group):
                t = w['text']
                if not eng_text:
                    eng_text = t
                else:
                    prev_w    = group[wi - 1]
                    pixel_gap = w['left'] - (prev_w['left'] + prev_w['width'])

                    last_char  = eng_text[-1]
                    first_char = t[0]
                    last_is_cjk  = _is_cjk(last_char)
                    first_is_cjk = _is_cjk(first_char)

                    if last_is_cjk and first_is_cjk:
                        if pixel_gap > grp_avg_char_w * 0.8:
                            eng_text += " " + t
                        else:
                            eng_text += t
                    else:
                        eng_text += " " + t
            print(f"-> '{eng_text}'")

    async def run_all():
        for file in test_files:
            await run_win_ocr(file)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_all())
