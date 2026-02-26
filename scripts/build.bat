@echo off
chcp 65001 >nul
:: 切換至專案根目錄
cd /d "%~dp0.."

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
:: 使用 --add-data 將 Tesseract-OCR 目錄打包進來
:: 使用 --icon 指定打包出來的 EXE 圖示
:: 新增 --exclude-module 來排除不必要的龐大套件，為打包瘦身
pyinstaller --noconsole --name "SnapTrans" --add-data "Tesseract-OCR;Tesseract-OCR" --icon="icon/icon.ico" --exclude-module scipy --exclude-module pandas --exclude-module matplotlib --exclude-module numpy --exclude-module IPython --exclude-module PyQt5.QtNetwork --exclude-module PyQt5.QtQml --exclude-module PyQt5.QtSql --exclude-module PyQt5.QtWebSockets --exclude-module PyQt5.QtWebEngineCore --exclude-module PyQt5.QtBluetooth --exclude-module tkinter main.py

if %errorlevel%==0 (
    echo.
    echo ✅ 打包完成！
    echo 📁 執行檔位於：dist\SnapTrans\SnapTrans.exe
) else (
    echo.
    echo ❌ 打包失敗！請檢查錯誤訊息。
)

echo.
exit /b
