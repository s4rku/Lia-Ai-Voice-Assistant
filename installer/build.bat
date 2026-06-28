@echo off
setlocal enabledelayedexpansion

echo.
echo  ============================================
echo   Sarku – Build Standalone Executable
echo  ============================================
echo.

:: Activate venv
if not exist "..\\.venv\\Scripts\\activate.bat" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    pause & exit /b 1
)
call ..\\.venv\\Scripts\\activate.bat

:: Install PyInstaller if needed
python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo [*] Installing PyInstaller...
    pip install pyinstaller==6.6.0 --quiet
)

:: Clean previous build
if exist "..\dist" rmdir /s /q "..\dist"
if exist "..\build" rmdir /s /q "..\build"

echo [*] Building executable...
cd ..
pyinstaller ^
    --name "Sarku" ^
    --onefile ^
    --windowed ^
    --icon "installer\sarku.ico" ^
    --add-data "assistant\config;assistant\config" ^
    --add-data ".env.example;." ^
    --hidden-import "assistant.ai.brain" ^
    --hidden-import "assistant.memory.store" ^
    --hidden-import "assistant.automation.dispatcher" ^
    --hidden-import "assistant.browser.controller" ^
    --hidden-import "assistant.vision.screen" ^
    --hidden-import "assistant.gui.app" ^
    --hidden-import "aiosqlite" ^
    --hidden-import "sqlalchemy.dialects.sqlite" ^
    --collect-all "edge_tts" ^
    --collect-all "faster_whisper" ^
    --noconfirm ^
    assistant\main.py

if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause & exit /b 1
)

echo.
echo  Build complete! Executable: dist\Sarku.exe
echo.
pause
