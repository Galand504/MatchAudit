"""Generate a synthetic screen-capture image of a known data table.

Produces ``sample-capture.png`` — an 800×400 white-background image
that simulates a SQL/CRUD query result with a 4-column, 5-row table
(or the row count passed via ``--rows``).

Usage::

    python tests/fixtures/gen_capture_fixture.py          # 5 rows
    python tests/fixtures/gen_capture_fixture.py --rows 3  # custom rows
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Known test data
# ---------------------------------------------------------------------------
HEADER = ["id", "name", "amount", "date"]
DATA = [
    ["1",   "Alice",     "1250.50", "2024-01-15"],
    ["2",   "Bob",       "3400.00", "2024-02-20"],
    ["3",   "Charlie",   "780.25",  "2024-03-10"],
    ["4",   "Diana",     "2100.75", "2024-04-05"],
    ["5",   "Eve",       "5600.00", "2024-05-22"],
]

# ---------------------------------------------------------------------------
# Layout constants (pixels)
# ---------------------------------------------------------------------------
COL_WIDTHS = [80, 160, 140, 160]       # per-column widths
ROW_HEIGHT = 42                         # per-row height
HEADER_HEIGHT = 42                      # header row height
MARGIN_X = 20                           # left/right margin
MARGIN_Y = 20                           # top/bottom margin
TABLE_WIDTH = sum(COL_WIDTHS)           # total table width
TABLE_HEIGHT = HEADER_HEIGHT + ROW_HEIGHT * 5  # total table height
IMG_WIDTH = TABLE_WIDTH + MARGIN_X * 2
IMG_HEIGHT = TABLE_HEIGHT + MARGIN_Y * 2

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
LIGHT_GRAY = (240, 240, 240)


def draw_table(draw: ImageDraw, rows: list[list[str]], font) -> None:
    """Draw a bordered table with header and data rows."""
    col_starts: list[int] = []
    x = MARGIN_X
    for w in COL_WIDTHS:
        col_starts.append(x)
        x += w

    y = MARGIN_Y

    # --- Header row (with light-gray background) ---
    for ci, col_name in enumerate(HEADER):
        cx = col_starts[ci]
        draw.rectangle([cx, y, cx + COL_WIDTHS[ci], y + HEADER_HEIGHT],
                       fill=LIGHT_GRAY, outline=BLACK)
        # Center text in cell
        bbox = draw.textbbox((0, 0), col_name, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((cx + (COL_WIDTHS[ci] - tw) / 2,
                   y + (HEADER_HEIGHT - th) / 2 - 2),
                  col_name, fill=BLACK, font=font)

    y += HEADER_HEIGHT

    # --- Data rows ---
    for ri, row_data in enumerate(rows):
        for ci, cell_text in enumerate(row_data):
            cx = col_starts[ci]
            draw.rectangle([cx, y, cx + COL_WIDTHS[ci], y + ROW_HEIGHT],
                           fill=WHITE, outline=BLACK)
            bbox = draw.textbbox((0, 0), cell_text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            # Left-align text with padding for readability
            draw.text((cx + 8, y + (ROW_HEIGHT - th) / 2 - 2),
                      cell_text, fill=BLACK, font=font)
        y += ROW_HEIGHT


def build_image(output_path: Path, rows: int = 5) -> None:
    """Create a synthetic capture PNG at *output_path*."""
    img_height = MARGIN_Y * 2 + HEADER_HEIGHT + ROW_HEIGHT * rows

    img = Image.new("RGB", (IMG_WIDTH, img_height), WHITE)
    draw = ImageDraw.Draw(img)

    # Try common mono-spaced fonts; fall back to default
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    ]:
        try:
            font = ImageFont.truetype(candidate, 16)
            break
        except (IOError, OSError):
            continue
    else:
        font = ImageFont.load_default()

    draw_table(draw, DATA[:rows], font)
    img.save(output_path, "PNG")
    print(f"Fixture saved: {output_path} ({img.size[0]}×{img.size[1]})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic capture fixture for OCR tests."
    )
    parser.add_argument(
        "--rows", type=int, default=5,
        help="Number of data rows (default: 5).",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output path (default: tests/fixtures/sample-capture.png).",
    )
    args = parser.parse_args()

    if args.output:
        out = Path(args.output)
    else:
        out = Path(__file__).resolve().parent / "sample-capture.png"

    build_image(out, rows=args.rows)


if __name__ == "__main__":
    main()
