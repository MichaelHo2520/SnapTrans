@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ==========================================
:: ✅ 專案部署參數 - 修改這區即可
:: ==========================================
set "PROJECT_NAME=SnapTrans (螢幕截圖翻譯工具)"
:: 使用目前的相對路徑搭配絕對目錄
set "CURRENT_DIR=%~dp0"
:: 由於建置產物預設是資料夾，我們複製整個 dist\SnapTrans 目錄內容或單一執行檔
:: 但是如果是目錄打包 (pyinstaller 預設)，執行檔會在 dist\SnapTrans\SnapTrans.exe，但周邊還有很多 dll
:: 為了方便，我們假設佈署整個資料夾。或者如果是 --onefile，就是一個檔案。
:: 為了相容性，目前 build.bat 是產生資料夾結構，因此來源為資料夾。
set "SOURCE_DIR=%CURRENT_DIR%dist\SnapTrans"

:: ✅ 多個目標資料夾，用 ; 分隔 
:: 請根據您的需求修改底下的目標路徑
set "TARGETS=C:\Users\q11948aa\Desktop\SnapTrans_Deploy_Test;\\xisrv1\FileServer\RD\Department\Michael\小工具\SnapTrans"
:: ==========================================

echo 🔧 專案名稱：%PROJECT_NAME%
echo 📄 來源目錄：%SOURCE_DIR%
echo.

:: 檢查來源
if not exist "%SOURCE_DIR%" (
    echo ❌ 找不到來源的目錄：%SOURCE_DIR%
    echo 💡 請先執行 build.bat 進行打包！
    pause
    exit /b
)

:: ===== 關鍵修正：用延遲變數解析 ; 分隔字串 =====
set "TARGET_LIST=%TARGETS%"
:split_loop
for /f "delims=;" %%A in ("!TARGET_LIST!") do (
    set "CURRENT_TARGET=%%A"
    call :deploy_to_target "!CURRENT_TARGET!"
    set "TARGET_LIST=!TARGET_LIST:*;=!"
    if not "!TARGET_LIST!"=="!CURRENT_TARGET!" goto split_loop
)

echo 🏁 所有部署已完成！
pause
exit /b

:: ==========================
:deploy_to_target
setlocal
set "TARGET_PATH=%~1"
echo 🔸 處理目標路徑：%TARGET_PATH%

if not exist "%TARGET_PATH%" (
    echo 📂 目標不存在，正在建立...
    mkdir "%TARGET_PATH%"
)

echo 📁 複製整個目錄到 %TARGET_PATH% ...
:: 使用 xcopy 來複製整個目錄架構，包含子目錄與隱藏檔。
:: /E 複製所有子目錄，/Y 不提示直接覆寫，/I 如果目標不存在視為目錄，/Q 安靜模式
xcopy /E /Y /I /Q "%SOURCE_DIR%" "%TARGET_PATH%"

if %errorlevel%==0 (
    echo ✅ 已成功部署到 %TARGET_PATH%
) else (
    echo ❌ 複製失敗，請檢查權限或網路狀態。
)

echo.
endlocal
goto :eof
