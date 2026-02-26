from PIL import Image
import os

# 設定輸入與輸出
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PNG = os.path.join(base_dir, "icon", "icon.png")
OUTPUT_ICO = os.path.join(base_dir, "icon", "icon.ico")

def create_ico():
    if not os.path.exists(INPUT_PNG):
        print(f"❌ 找不到 {INPUT_PNG}，請確認檔名！")
        return

    try:
        img = Image.open(INPUT_PNG)
        
        # 轉成 ICO，並包含多種尺寸 (Windows 標準)
        # 這樣不管是在清單檢視還是在大圖示檢視都清晰
        img.save(OUTPUT_ICO, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        
        print(f"✅ 成功轉換！已產生標準 ICO 檔：{OUTPUT_ICO}")
        print("➡️ 請去修改您的 .spec 檔，把 icon 指向這個新檔案。")
        
    except Exception as e:
        print(f"❌ 轉換失敗: {e}")

if __name__ == "__main__":
    create_ico()