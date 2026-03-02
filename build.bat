@echo off
echo ==============================================
echo  SnapTrans Build ^& Installer Script
echo ==============================================
echo.

:: 1. 啟動虛擬環境 (如果存在的話)
if exist .venv\Scripts\activate.bat (
    echo [1/3] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo [1/3] Virtual environment not found. Proceeding with global Python...
)

:: 2. 執行 PyInstaller 打包成資料夾
echo [2/3] Building with PyInstaller (Directory Mode)...
pyinstaller --clean -y SnapTrans.spec
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b %ERRORLEVEL%
)

:: 3. 呼叫 Inno Setup 編譯器
echo [3/3] Compiling Inno Setup installer...
:: Check standard installation paths for Inno Setup (ISCC.exe)
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

if exist "%ISCC%" (
    "%ISCC%" setup.iss
    if %ERRORLEVEL% neq 0 (
        echo.
        echo [ERROR] Inno Setup compilation failed.
        pause
        exit /b %ERRORLEVEL%
    )
    echo.
    echo ==============================================
    echo  Build Successful! Installer is in the 'deploy' folder.
    echo ==============================================
) else (
    echo.
    echo [WARNING] Inno Setup compiler (ISCC.exe) not found!
    echo Please install Inno Setup 6 from https://jrsoftware.org/
    echo The portable build is ready at 'dist\SnapTrans' anyway.
)

pause
