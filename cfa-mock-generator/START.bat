@echo off
title CFA MockGen - Starting...

:: Change to the directory where this .bat file is located
cd /d "%~dp0"

echo.
echo  ============================================================
echo    CFA MockGen - CFA Level I Mock Exam Generator
echo  ============================================================
echo.
echo  Running from: %cd%
echo.

:: Create data directories
if not exist "data" mkdir data
if not exist "data\uploads" mkdir data\uploads

:: Install dependencies
echo  Installing dependencies...
pip install -r requirements.txt -q 2>nul
if errorlevel 1 (
    echo  [!] pip failed. Trying with python -m pip...
    python -m pip install -r requirements.txt -q 2>nul
)
echo  [OK] Dependencies ready.
echo.

:: Open browser after a short delay
echo  Starting server...
echo  Your browser will open automatically.
echo  Keep this window open while using the app.
echo.
echo  ============================================================
echo    http://localhost:5000
echo  ============================================================
echo.

:: Open browser in background after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: Start the server
python backend/app.py

:: If server stops
echo.
echo  Server stopped. Press any key to exit.
pause >nul
