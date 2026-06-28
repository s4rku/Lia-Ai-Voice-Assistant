@echo off
setlocal enabledelayedexpansion

echo.
echo  ███████╗ █████╗ ██████╗ ██╗  ██╗██╗   ██╗
echo  ██╔════╝██╔══██╗██╔══██╗██║ ██╔╝██║   ██║
echo  ███████╗███████║██████╔╝█████╔╝ ██║   ██║
echo  ╚════██║██╔══██║██╔══██╗██╔═██╗ ██║   ██║
echo  ███████║██║  ██║██║  ██║██║  ██╗╚██████╔╝
echo  ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝
echo.
echo  AI Voice Assistant for Windows - Setup
echo  ========================================
echo.

:: Check Python version
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.12+ from https://python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER% found.

:: Create virtual environment
if not exist ".venv" (
    echo [*] Creating virtual environment...
    python -m venv .venv
) else (
    echo [OK] Virtual environment already exists.
)

:: Activate venv
call .venv\Scripts\activate.bat

:: Upgrade pip
echo [*] Upgrading pip...
python -m pip install --upgrade pip --quiet

:: Install dependencies
echo [*] Installing dependencies (this may take a few minutes)...
pip install -r requirements.txt --quiet

:: Copy .env if not present
if not exist ".env" (
    echo [*] Creating .env from template...
    copy .env.example .env >nul
    echo [!] IMPORTANT: Edit .env and add your OPENAI_API_KEY before running lia.
) else (
    echo [OK] .env already exists.
)

:: Create data directories
if not exist "data\memory" mkdir data\memory
if not exist "data\models" mkdir data\models
if not exist "data\screenshots" mkdir data\screenshots

echo.
echo  Setup complete!
echo  ──────────────
echo  1. Edit .env and add your API keys
echo  2. Run:  .venv\Scripts\activate
echo  3. Run:  python -m assistant.main
echo.
pause
