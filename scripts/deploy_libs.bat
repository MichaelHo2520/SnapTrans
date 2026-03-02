@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ==========================================
:: ✅ 專案佈署參數 (Libraries/Framework)
:: ==========================================
set "PROJECT_NAME=SnapTrans (Libraries 更新)"
set "CURRENT_DIR=%~dp0..\"
set "SOURCE_DIR=%CURRENT_DIR%dist\SnapTrans"

:: ✅ 多個目標資料夾，用 ; 分隔 
set "TARGETS=C:\Users\q11948aa\Documents\SnapTrans;\\xisrv1\FileServer\RD\Department\Michael\小工具\SnapTrans"
:: ==========================================

echo 🔧 專案名稱：%PROJECT_NAME%
echo 📄 來源目錄：%SOURCE_DIR%
echo.

:: 檢查來源
if not exist "%SOURCE_DIR%" (
    echo ❌ 找不到來源的目錄：%SOURCE_DIR%
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

echo 🏁 Tüm Libraries 部署已完成！
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

echo 📁 複製整個目錄(包含 DLLs, Tesseract) 到 %TARGET_PATH% ...
:: 複製所有檔案(含子目錄)，但不提示覆寫、不複製空目錄
xcopy /E /Y /I /Q "%SOURCE_DIR%" "%TARGET_PATH%" >nul

if %errorlevel%==0 (
    echo ✅ 已成功部署 Libraries 到 %TARGET_PATH%
) else (
    echo ❌ 複製失敗，請檢查權限或網路狀態。
)

echo.
endlocal
goto :eof
