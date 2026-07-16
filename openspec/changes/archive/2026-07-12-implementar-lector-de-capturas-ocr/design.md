# Design: OcrReader

## Architecture

```
CLI (click)
  │
  ├── detect_reader()           ← Lazy registry (CsvReader, ExcelReader, OcrReader)
  │     └── OcrReader           ← If easyocr importable
  │
  └── --ocr flag bypass
        └── OcrReader(...)      ← Direct instantiation (forces OCR)
              │
              └── read(path)
                    ├── Image.open() → np.array
                    ├── _get_easyocr()  ← Lazy singleton (first call creates Reader)
                    ├── reader.readtext(img_array)
                    ├── Filter by conf_threshold
                    ├── _group_by_rows()  ← Y-centre clustering
                    ├── _detect_header()  ← Alpha-ratio heuristic
                    └── _build_dataframe() ← Column names + padding
```

## Key Design Decisions

### ADR-1: EasyOCR Lazy Singleton

**Decision**: EasyOCR `Reader` is created once on first `read()` call and cached as a module-level `_OCR_INSTANCE` global.

**Rationale**: EasyOCR model loading takes 5–15 seconds on CPU. Creating a singleton avoids this cost on import and on repeated reads. Lazy initialization means `OcrReader` can be imported / registered without triggering the download or model load.

**Consequence**: First `read()` call is slow (~5-15s). Subsequent reads reuse the loaded model.

### ADR-2: Row Grouping by Y-Centre with np.median Tolerance

**Decision**: Detections are grouped into rows by comparing each detection's Y-centre against a threshold derived from `np.median(all_heights) * row_height_tolerance`.

**Rationale**: OCR bounding boxes have varying heights (descenders, ascenders, different font sizes). Using median height as a baseline is robust to outliers. The tolerance factor (default 0.6) allows reasonable vertical drift within a row while separating actual distinct rows.

**Edge cases handled**:
- Empty results → empty list
- Single row → single group
- Close rows → configurable merge via tolerance

### ADR-3: Header Detection by Alphabetic Ratio

**Decision**: The header row is heuristically identified as the first row where >40% of non-empty cells contain at least one alphabetic character.

**Rationale**: Column headers almost always contain text labels (`"Name"`, `"Date"`, `"Amount"`), while data rows in audit contexts are predominantly numeric. The 40% threshold is intentionally conservative to avoid misclassifying sparse numeric data as header.

**Edge cases handled**:
- All-numeric rows → `None` (no header)
- First row empty → skip to next row
- Second row has alpha content → return index 1

### ADR-4: DataFrame Builder with None-Padding

**Decision**: Uneven rows (detected cells misaligned per column) are padded with `None` rather than raising or truncating.

**Rationale**: OCR detections can miss cells or produce extra fragments. Padding with `None` preserves alignment so downstream comparison still works — the missing cell appears as a null rather than a misaligned value.

### ADR-5: Lazy Registration with ImportError Catch

**Decision**: `OcrReader` is registered in `_ensure_readers()` inside a `try/except ImportError` block.

**Rationale**: EasyOCR is an optional dependency. The reader registry must never crash when easyocr is absent. Catching `ImportError` at registration time means `detect_reader()` gracefully degrades — it raises a helpful `ValueError` for image files with installation instructions rather than an `ImportError` traceback.

### ADR-6: Constructor + kwargs Override in read()

**Decision**: Configuration parameters (`conf_threshold`, `language`, `row_tolerance`, etc.) can be set via constructor AND overridden per-call via `**kwargs` in `read()`.

**Rationale**: This gives callers flexibility — set defaults at construction time and override for specific files without creating a new reader instance.

### ADR-7: Conf Threshold Filter Post-OCR

**Decision**: Confidence threshold filtering is applied after `reader.readtext()` returns results, not passed as an EasyOCR parameter.

**Rationale**: EasyOCR's built-in `min_size` and low-confidence filtering are less transparent. Post-filtering gives us explicit control and makes the threshold visible and testable. Detections below threshold are simply discarded before row grouping.

### ADR-8: CLI Flag --ocr Bypasses detect_reader

**Decision**: `--ocr` flag in CLI creates `OcrReader` directly, bypassing `detect_reader()` entirely.

**Rationale**: `detect_reader()` only knows extension-to-reader mappings. The `--ocr` flag is an explicit override — "treat this file as an image, regardless of extension". Direct construction is the simplest way to bypass the factory while reusing the same reader class.

## Sequence: OcrReader.read() without header override

```
caller                    OcrReader              _get_easyocr()       EasyOCR Reader
  │                          │                       │                     │
  │──read("capture.png")─────│                       │                     │
  │                          │──_get_easyocr()───────│                     │
  │                          │                       │──Reader(["en"])────│
  │                          │                       │   (5-15s first call)│
  │                          │<─────reader instance──│                     │
  │                          │──readtext(img_array)───────────────────────│
  │                          │<─────────── detections ────────────────────│
  │                          │──filter by conf_threshold                  │
  │                          │──_group_by_rows(detections)                │
  │                          │──_detect_header(rows)                      │
  │                          │──_build_dataframe(data, header)            │
  │<──────────DataFrame──────│                                             │
```

## Error Handling

| Scenario | Mechanism | Behaviour |
|----------|-----------|-----------|
| File not found | `path.exists()` check | Raises `FileNotFoundError` |
| EasyOCR not installed | `try/except ImportError` in `_get_easyocr()` | Raises `ImportError` with `pip install` hint |
| CLI --ocr without easyocr | Pre-check in CLI handler | `click.echo(err=True)` + `SystemExit(1)` |
| Unknown file extension | `detect_reader()` fallthrough | Raises `ValueError` mentioning supported formats |
| Image without easyocr | `_ensure_readers()` misses OcrReader | `detect_reader()` raises `ValueError` with install hint |

## Configuration Surface

```
OcrReader(
    conf_threshold=0.3,       # Minimum confidence (0-1)
    language=["en"],          # EasyOCR language list
    row_tolerance=0.6,        # Y-centre grouping tolerance (fraction of median height)
    header_rows=None,         # None=auto-detect, int=explicit count
    allowlist=None,           # Characters allowed by EasyOCR engine
)
```

CLI flags override constructor defaults at call time via `**kwargs` in `read()`.
