# -*- mode: python ; coding: utf-8 -*-
#
# MatchAudit — PyInstaller spec
# ==============================
# Build with:
#   pyinstaller scripts/MatchAudit.spec
#
# Produces a portable ``dist/MatchAudit/MatchAudit.exe`` (or equivalent on
# Linux/macOS) with no Python or dependency installation required.

import os
import site
import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
# __file__ is NOT defined inside a .spec (exec'd by PyInstaller), so we
# derive the project root from CWD — the user must run from the repo root:
#   pyinstaller scripts\MatchAudit.spec
PROJECT_ROOT = Path(os.getcwd()).resolve()
SRC = PROJECT_ROOT / "src"

# Collect ALL site-packages dirs (system + user) — Windows Store Python
# may install packages in user-local paths that getsitepackages() misses.
_user_site = site.getusersitepackages()
_site_dirs = site.getsitepackages() + ([_user_site] if isinstance(_user_site, str) else _user_site)
ALL_SITE = [Path(d) for d in _site_dirs if d and Path(d).is_dir()]
# VENV_SITE is the first existing dir (used for EasyOCR data lookup)
VENV_SITE = ALL_SITE[0] if ALL_SITE else Path(sys.prefix) / "Lib" / "site-packages"
print(f"  Site packages: {[str(d) for d in ALL_SITE]}")

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
        "matchaudit.readers.csv",
        "matchaudit.readers.excel",

        # -- EasyOCR (data dirs handled by Tree() below) --
        "easyocr",

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

# ── Collect packages from ALL site dirs (user + system) ──────────────────
# Windows Store Python installs packages in user-local paths that
# getsitepackages() may miss. collect_all searches sys.path at runtime.
from PyInstaller.utils.hooks import collect_all as _collect_all
for pkg in ("pandas", "numpy", "openpyxl", "customtkinter", "darkdetect",
            "easyocr", "torch", "torchvision", "opencv-python-headless",
            "scikit-image", "Pillow"):
    try:
        datas, binaries, hiddenimports = _collect_all(pkg)
        a.datas += datas
        a.binaries += binaries
        a.hiddenimports += hiddenimports
        print(f"  ✓ collect_all({pkg}): {len(datas)} datas, {len(binaries)} binaries")
    except Exception as exc:
        print(f"  ⚠ collect_all({pkg}) failed: {exc}")

# ── Collect any ·.pth / ·.onnx model files that torch may need at init ──
for site_dir in ALL_SITE:
    for pth in site_dir.rglob("*.pth"):
        a.binaries.append((pth.name, str(pth), "BINARY"))

# ── PYZ ──────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── EXE (the launcher — scripts only for one-folder mode) ───────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,              # binaries go via COLLECT
    name="MatchAudit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=True,                      # TEMP: console for debugging; change to False once OCR works
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
