@echo off
REM ============================================================================
REM  MatchAudit — Windows build script
REM ============================================================================
REM  Builds a portable .exe with PyInstaller.
REM  Run from the project root (where pyproject.toml lives).
REM
REM  Prerequisites:
REM    1. Python 3.11+ installed
REM    2. uv installed (https://docs.astral.sh/uv/)
REM
REM  Usage:
REM    1. Open a terminal in the project root
REM    2. Run:  scripts\build.bat
REM    3. Find the portable folder at:  dist\MatchAudit\
REM
REM  The resulting folder can be zipped and distributed — no Python needed.
REM ============================================================================

echo.
echo === MatchAudit — Building portable executable ===
echo.

REM ---- 1. Install everything -------------------------------------------------
echo [1/4] Installing dependencies (OCR + GUI)...
call uv sync --extra ocr --extra gui
if %ERRORLEVEL% neq 0 (
    echo ERROR: uv sync failed. Make sure uv is installed.
    exit /b %ERRORLEVEL%
)

REM ---- 2. Install PyInstaller ------------------------------------------------
echo [2/4] Installing PyInstaller...
call uv pip install pyinstaller
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

REM ---- 3. Pre-download EasyOCR models (optional, speeds up first launch) -----
echo [3/4] Pre-downloading EasyOCR models...
uv run python -c "import easyocr; easyocr.Reader(['es', 'en'], gpu=False)" 2>nul
echo      (OK if it warns about GPU — models are cached)

REM ---- 4. Build --------------------------------------------------------------
echo [4/4] Building executable with PyInstaller...
echo.
echo      This may take 5-15 minutes and use significant RAM.
echo      The output will be in dist\MatchAudit\
echo.
call pyinstaller --clean scripts\MatchAudit.spec
if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller build failed.
    exit /b %ERRORLEVEL%
)

REM ---- Done ------------------------------------------------------------------
echo.
echo === BUILD COMPLETE ===
echo.
echo Portable folder:  dist\MatchAudit\
echo Launcher:         dist\MatchAudit\MatchAudit.exe
echo.
echo To distribute, zip the entire MatchAudit folder.
echo.
pause
