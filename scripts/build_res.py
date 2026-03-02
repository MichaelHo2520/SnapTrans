# build_res.py
# 這個腳本只需執行一次，用來把圖片轉成程式碼
import os

def png_to_py():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon_path = os.path.join(base_dir, "icon", "icon.png")
    out_path = os.path.join(base_dir, "icon_data.py")
    
    if not os.path.exists(icon_path):
        print(f"錯誤: 找不到 {icon_path}，請確認檔案存在。")
        return

    # 讀取圖片的二進位數據
    with open(icon_path, "rb") as f:
        data = f.read()

    # 寫入成 Python 檔案
    with open(out_path, "w") as f:
        f.write(f"# Auto-generated icon data\n")
        f.write(f"ICON_PNG_BYTES = {data!r}\n")
    
    print("成功！已建立 icon_data.py，圖片已嵌入程式碼中。")

if __name__ == "__main__":
    png_to_py()