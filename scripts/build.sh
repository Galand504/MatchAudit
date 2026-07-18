#!/usr/bin/env bash
# ============================================================================
#  MatchAudit — Linux/macOS build script
# ============================================================================
#  Builds a portable executable with PyInstaller.
#  Run from the project root (where pyproject.toml lives).
#
#  Prerequisites:
#    1. Python 3.11+ installed
#    2. uv installed (https://docs.astral.sh/uv/)
#
#  Usage:
#    ./scripts/build.sh
#
#  Output:  dist/MatchAudit/
# ============================================================================

set -euo pipefail

echo ""
echo "=== MatchAudit — Building portable executable ==="
echo ""

# ---- 1. Install everything -------------------------------------------------
echo "[1/4] Installing dependencies (OCR + GUI)..."
uv sync --extra ocr --extra gui

# ---- 2. Install PyInstaller ------------------------------------------------
echo "[2/4] Installing PyInstaller..."
uv pip install pyinstaller

# ---- 3. Pre-download EasyOCR models -----------------------------------------
echo "[3/4] Pre-downloading EasyOCR models..."
uv run python -c "import easyocr; easyocr.Reader(['es', 'en'], gpu=False)" 2>/dev/null || true
echo "      (OK if it warns about GPU — models are cached)"

# ---- 4. Build --------------------------------------------------------------
echo "[4/4] Building executable with PyInstaller..."
echo ""
echo "      This may take 5–15 minutes and use significant RAM."
echo ""
uv run pyinstaller --clean scripts/MatchAudit.spec

# ---- Done ------------------------------------------------------------------
echo ""
echo "=== BUILD COMPLETE ==="
echo ""
echo "Portable folder:  dist/MatchAudit/"
echo "Launcher:         dist/MatchAudit/MatchAudit"
echo ""
echo "To distribute, tar/zip the entire MatchAudit folder."
echo ""
