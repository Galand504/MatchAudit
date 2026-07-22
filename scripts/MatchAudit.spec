# -*- mode: python ; coding: utf-8 -*-
#
# MatchAudit — PyInstaller spec
# ==============================
# Build with:
#   pyinstaller scripts/MatchAudit.spec
#
# Produces a portable ``dist/MatchAudit/MatchAudit.exe`` (or equivalent on
# Linux/macOS) with no Python or dependency installation required.

import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
# All paths are relative to the project root (where this spec lives).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "src"
VENV_SITE = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"

# ── Block cipher ─────────────────────────────────────────────────────────
block_cipher = None

# ── Analysis ─────────────────────────────────────────────────────────────
# Collect the main entry point and all module dependencies.
a = Analysis(
    [str(SRC / "matchaudit" / "gui.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # -- matchaudit itself --
        "matchaudit.cli",
        "matchaudit.core.comparator",
        "matchaudit.core.models",
        "matchaudit.core.control_point",
        "matchaudit.output.console",
        "matchaudit.readers",
        "matchaudit.readers.ocr",
        "matchaudit.readers.csv_reader",
        "matchaudit.readers.excel_reader",

        # -- EasyOCR --
        "easyocr",
        "easyocr.character",
        "easyocr.weights",
        "easyocr.utils",
        "easyocr.imgproc",

        # -- torch (CPU) --
        "torch",
        "torchvision",
        "torch.nn",

        # -- image I/O --
        "PIL",
        "PIL._imaging",
        "PIL.ImageEnhance",
        "PIL.ImageOps",
        "cv2",
        "skimage",
        "skimage.transform",
        "skimage.filters",
        "skimage.morphology",
        "skimage.measure",
        "skimage.color",

        # -- data --
        "pandas",
        "openpyxl",
        "numpy",

        # -- GUI --
        "customtkinter",
        "darkdetect",

        # -- CLI (indirect) --
        "click",
        "rich",
        "rich.table",
        "rich.panel",
        "rich.console",
        "rich.columns",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "IPython",
        "jupyter",
        "jupyter_client",
        "notebook",
        "qtpy",
        "PyQt5",
        "PySide2",
        "PySide6",
        "wx",
        "test",
        "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── Collect EasyOCR data files ───────────────────────────────────────────
# EasyOCR ships model weights and character lists inside its package dir.
# These must be bundled or the OCR engine will fail at runtime.
_easyocr_dir = VENV_SITE / "easyocr"
if _easyocr_dir.is_dir():
    for sub in ("character", "weights"):
        src = _easyocr_dir / sub
        if src.is_dir():
            a.datas += Tree(str(src), prefix=f"easyocr/{sub}")
            print(f"  ✓ Bundled easyocr/{sub}")

# ── Collect any ·.pth / ·.onnx model files that torch may need at init ──
# This catches craft / recognition model files that live outside easyocr.
for pth in VENV_SITE.rglob("*.pth"):
    a.binaries.append((pth.name, str(pth), "BINARY"))

# ── PYZ ──────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── EXE (the launcher) ──────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MatchAudit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        "torch*",
        "libtorch*",
        "caffe2*",
        "c10*",
        "libc10*",
        "libshm*",
        "libgomp*",
        "libiomp*",
    ],
    runtime_tmpdir=None,
    console=False,                     # no terminal window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                         # optional: str(ICON) 
)

# ── COLLECT (onedir — folder output) ────────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        "torch*",
        "libtorch*",
        "caffe2*",
        "c10*",
        "libc10*",
        "libshm*",
        "libgomp*",
        "libiomp*",
    ],
    name="MatchAudit",
)
