@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ==========================================
echo   🚀 SnapTrans (螢幕截圖翻譯工具) 打包腳本
echo ==========================================
echo 正在安裝/更新打包必備套件 (PyInstaller)...
pip install pyinstaller

echo.
echo 正在清理舊的建置檔案...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q *.spec 2>nul

echo.
echo 開始打包專案...
:: 我們使用 --noconsole 隱藏背景的終端機視窗，並命名為 SnapTrans
pyinstaller --noconsole --name "SnapTrans" main.py

if %errorlevel%==0 (
    echo.
    echo ✅ 打包完成！
    echo 📁 執行檔位於：dist\SnapTrans\SnapTrans.exe
) else (
    echo.
    echo ❌ 打包失敗！請檢查錯誤訊息。
)

echo.
pause
exit /b
