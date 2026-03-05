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

:: Using direct IF EXIST and GOTO to avoid bat variable parsing issues with parenthesis
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup.iss
    goto skip_iscc_fallback
)

if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    "C:\Program Files\Inno Setup 6\ISCC.exe" setup.iss
    goto skip_iscc_fallback
)

:: If we reach here, neither standard path was found
echo.
echo [WARNING] Inno Setup compiler (ISCC.exe) not found!
echo Please install Inno Setup 6 from https://jrsoftware.org/
echo The portable build is ready at 'dist\SnapTrans' anyway.
pause
exit /b 0

:skip_iscc_fallback

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
pause
