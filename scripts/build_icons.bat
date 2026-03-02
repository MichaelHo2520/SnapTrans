@echo off
chcp 65001 >nul
:: 切換至專案根目錄
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8

echo ==========================================
echo   🎨 SnapTrans (圖示產生腳本)
echo ==========================================
echo 正在準備圖示資源...

:: 備份原始圖示 (如果 icon_base.png 不存在而且 icon.png 存在，那就把 icon.png 改名保證原始檔不丟失)
if exist "icon\icon.png" (
    if not exist "icon\icon_base.png" (
        rename "icon\icon.png" "icon_base.png"
        echo 檔案備份: 將原始 icon.png 標記為 icon_base.png
    ) else (
        echo 🚨 注意: icon_base.png 已經存在，正在直接使用新放入的 icon.png 覆蓋...
        :: 因為要直接拿新的 icon.png 來用，先把它強制蓋過去給後續腳本讀
        copy /Y "icon\icon.png" "icon\icon_base.png" >nul
    )
)

python scripts\crop_icon.py
python scripts\build_res.py
python scripts\make_ico.py

echo.
echo ✅ 圖示產生完成！
exit /b
