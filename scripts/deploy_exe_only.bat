@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ==========================================
:: ✅ 專案部署參數 - 修改這區即可
:: ==========================================
set "PROJECT_NAME=SnapTrans (螢幕截圖翻譯工具)"
:: 使用目前的相對路徑搭配絕對目錄 (回到專案根目錄)
set "CURRENT_DIR=%~dp0..\"
:: 只佈署建置出來的 .exe 執行檔
set "SOURCE_EXE=%CURRENT_DIR%dist\SnapTrans\SnapTrans.exe"

:: ✅ 多個目標資料夾，用 ; 分隔 
:: 請根據您的需求修改底下的目標路徑
set "TARGETS=C:\Users\q11948aa\Documents\SnapTrans;\\xisrv1\FileServer\RD\Department\Michael\小工具\SnapTrans"
:: ==========================================

echo 🔧 專案名稱：%PROJECT_NAME%
echo 📄 來源 EXE：%SOURCE_EXE%
echo.

:: 檢查來源
if not exist "%SOURCE_EXE%" (
    echo ❌ 找不到來源的 EXE 檔案：%SOURCE_EXE%
    echo 💡 請先執行 build.bat 進行打包！
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

echo 📁 複製 .exe 到 %TARGET_PATH% ...
copy /Y "%SOURCE_EXE%" "%TARGET_PATH%" >nul

if %errorlevel%==0 (
    echo ✅ 已成功部署到 %TARGET_PATH%
) else (
    echo ❌ 複製失敗，請檢查權限或網路狀態。
)

echo.
endlocal
goto :eof
