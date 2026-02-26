# crop_icon.py
import os
from PIL import Image, ImageDraw

def make_rounded_icon():
    # 取得路徑 (因為目前在 scripts 目錄下，退一層到專案根目錄)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 腳本現在會去讀取我們備份出來的 icon_base
    input_path = os.path.join(base_dir, 'icon', 'icon_base.png')
    output_path = os.path.join(base_dir, 'icon', 'icon.png')

    print(f"1. 正在讀取圖片: {input_path}")
    
    if not os.path.exists(input_path):
        print(f"錯誤: 找不到原始圖片 '{input_path}'")
        return

    # 開啟圖片並轉為 RGBA (為了透明度)
    img = Image.open(input_path).convert("RGBA")
    
    # 準備一個跟圖片一樣大的透明底圖
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    
    # 計算圓角半徑 (通常是寬度的 20% ~ 25% 最像 APP icon)
    w, h = img.size
    radius = int(min(w, h) * 0.25)
    
    # 畫一個白色的圓角矩形 (這就是餅乾模具，白色部分會被保留)
    draw.rounded_rectangle([(0, 0), (w, h)], radius=radius, fill=255)
    
    # 套用模具：將 mask 套用到圖片的 Alpha 通道
    # 這樣 mask 是黑色的地方(四個角)就會變透明，白色的地方(晶片)會保留
    img.putalpha(mask)
    
    # 存檔
    img.save(output_path, "PNG")
    print(f"2. 成功！已裁切出圓角圖示：{output_path}")
    print("   (藍色晶片已保留，四個尖角已變透明)")

if __name__ == "__main__":
    make_rounded_icon()