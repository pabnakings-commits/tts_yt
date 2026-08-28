@echo off
setlocal enabledelayedexpansion
title AI Voice Studio
cd /d "%~dp0"

echo ============================================
echo   AI Voice Studio - Local TTS (CPU Mode)
echo ============================================
echo.

REM --- 1. Check Python -------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on your PATH.
    echo Install Python 3.10-3.12 from https://www.python.org/downloads/
    echo and make sure "Add python.exe to PATH" is checked during setup.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VERSION=%%v
echo Found Python %PY_VERSION%

REM --- 2. Create / activate virtual environment -------------------------
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

REM --- 3. Install backend dependencies -----------------------------------
if not exist ".venv\.deps_installed" (
    echo Installing Python dependencies (first run only, this can take a few minutes)...
    python -m pip install --upgrade pip >nul
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install Python dependencies.
        pause
        exit /b 1
    )
    echo done > ".venv\.deps_installed"
) else (
    echo Python dependencies already installed, skipping.
)

REM --- 4. Check FFmpeg ----------------------------------------------------
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo.
    echo [WARNING] FFmpeg was not found on your PATH.
    echo   WAV export will still work, but MP3 export will not.
    echo   Install it with:  winget install ffmpeg
    echo   or download it from https://ffmpeg.org/download.html
    echo   Then restart this script.
    echo.
) else (
    echo FFmpeg found.
)

REM --- 5. Build the frontend (first run, or after frontend changes) ------
if not exist "frontend\dist\index.html" (
    where npm >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Node.js/npm was not found on your PATH.
        echo Install Node.js LTS from https://nodejs.org/ and re-run this script.
        pause
        exit /b 1
    )
    echo Building the web interface (first run only)...
    pushd frontend
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed.
        popd
        pause
        exit /b 1
    )
    call npm run build
    if errorlevel 1 (
        echo [ERROR] Frontend build failed.
        popd
        pause
        exit /b 1
    )
    popd
) else (
    echo Frontend already built, skipping.
)

REM --- 6. Model files ------------------------------------------------------
echo.
echo The Kokoro voice model (~320 MB) will be downloaded automatically on
echo the first generation if it isn't already cached in models\
echo.

REM --- 7. Start the server and open the browser ---------------------------
echo.
echo Starting AI Voice Studio...
echo   On this PC:              http://localhost:8000
echo   From your phone/tablet:  http://ADDRESS-BELOW:8000  (same Wi-Fi network)
echo.
echo Your PC's network address(es):
for /f "delims=" %%a in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -ne '127.0.0.1' }).IPAddress" 2^>nul') do (
    echo   http://%%a:8000
)
echo.
echo If this is the first time, Windows Firewall may ask to allow Python
echo to accept connections - choose "Allow access" (Private networks) so
echo other devices on your Wi-Fi can reach it.
echo.

start "" http://localhost:8000
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

pause
