# OCR Reader — Spec

## Domain: readers

### Requirement: OcrReader implements DataReader (R1)

The system MUST provide an `OcrReader` class that implements the `DataReader` ABC.

**Scenarios:**
- Given an `OcrReader` instance, when checking its type, THEN it MUST be a valid `DataReader` subclass
- The class MUST provide concrete implementations of `read()` and `supports()` as required by the ABC

### Requirement: Extension support (R2)

`OcrReader.supports()` MUST return `True` for `.png`, `.jpg`, and `.jpeg` extensions, and `False` for all others.

**Scenarios:**
- Given an `OcrReader` instance, when calling `supports(".png")`, THEN it MUST return `True`
- Given an `OcrReader` instance, when calling `supports(".jpg")`, THEN it MUST return `True`
- Given an `OcrReader` instance, when calling `supports(".jpeg")`, THEN it MUST return `True`
- Given an `OcrReader` instance, when calling `supports(".PNG")`, THEN it MUST return `True` (case-insensitive)
- Given an `OcrReader` instance, when calling `supports(".csv")` or `supports(".xlsx")`, THEN it MUST return `False`

### Requirement: Row grouping (R3)

The `_group_by_rows()` function MUST group EasyOCR detections into rows by Y-centre proximity using a configurable tolerance.

**Scenarios:**
- Given an empty results list, when grouping, THEN it MUST return an empty list
- Given detections from a single row (two cells at same Y level), when grouping, THEN they MUST be grouped into one sorted row
- Given detections from two distinct rows (separated by > tolerance * median_height), when grouping, THEN each row MUST be a separate group
- Given close rows within `row_height_tolerance`, when grouping, THEN they MAY merge into a single row

### Requirement: Header detection (R4)

The `_detect_header()` function MUST identify the header row heuristically based on alphabetic cell ratio.

**Scenarios:**
- Given rows where the first row has >40% alphabetic cells, when detecting header, THEN it MUST return index 0
- Given purely numeric rows (no alphabetic cells), when detecting header, THEN it MUST return `None`
- Given rows where the first row is empty and the second row has alpha cells, when detecting header, THEN it MUST return index 1
- Given a row with all empty cells, when detecting header, THEN it MUST be skipped

### Requirement: DataFrame building (R5)

The `_build_dataframe()` function MUST produce a `pandas.DataFrame` from row-grouped OCR detections.

**Scenarios:**
- Given a header row and data rows, when building DataFrame, THEN column names MUST come from the header row cells
- Given no header row, when building DataFrame, THEN columns MUST be named `col_0`, `col_1`, ...
- Given rows with unequal cell counts, when building DataFrame, THEN shorter rows MUST be padded with `None`

### Requirement: detect_reader integration (R6)

The `detect_reader()` factory MUST select `OcrReader` for image file extensions.

**Scenarios:**
- Given a `.png` file path, when detecting reader, THEN `OcrReader` MUST be selected
- Given a `.jpg` file path, when detecting reader, THEN `OcrReader` MUST be selected
- Given a `.jpeg` file path, when detecting reader, THEN `OcrReader` MUST be selected
- Given a `.png` file path without EasyOCR installed, when detecting reader, THEN the system MUST raise a descriptive `ValueError` mentioning easyocr installation

### Requirement: CLI --ocr flag (R7)

The `compare` command MUST support `--ocr`, `--ocr-language`, and `--ocr-conf-threshold` flags.

**Scenarios:**
- Given the CLI help output, when inspecting, THEN `--ocr`, `--ocr-language`, and `--ocr-conf-threshold` options MUST be visible

### Requirement: Graceful error without EasyOCR (R8)

When `--ocr` is used but EasyOCR is not installed, the system MUST report a clear error and exit gracefully.

**Scenarios:**
- Given the CLI with `--ocr` flag and EasyOCR not installed, when executing, THEN a clear error message MUST be printed to stderr and the process MUST exit with code 1

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `conf_threshold` | `0.3` | Minimum confidence to keep a detection (range 0–1) |
| `language` | `["en"]` | Language(s) for EasyOCR |
| `row_tolerance` | `0.6` | Fraction of median row height for Y-centre grouping |
| `header_rows` | `None` (auto-detect) | Explicit number of header rows |
| `allowlist` | `None` | Restricted character set for EasyOCR |

## Dependencies

- `easyocr` (optional, via `pip install matchaudit[ocr]`)
- `pillow`
- `numpy`
- `pandas`

## Non-requirements (out of scope)

- Multi-language OCR (only `["en"]` in this iteration)
- PDF, TIFF, BMP support (only PNG/JPEG)
- OpenCV preprocessing (postponed)
- Standalone OCR subcommand (pipeline-integrated only)
