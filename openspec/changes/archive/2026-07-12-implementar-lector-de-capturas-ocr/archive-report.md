# Archive Report: implementar-lector-de-capturas-ocr

**Archived**: 2026-07-12
**Branch**: feat/ocr-reader-02-wiring
**Mode**: openspec

## What Was Built

OCR reading capability for MatchAudit — transforms screenshot images (PNG/JPEG) into pandas DataFrames via EasyOCR, integrating into the existing comparison pipeline.

### Components

| Component | Type | Path |
|-----------|------|------|
| `OcrReader` | New | `src/matchaudit/readers/ocr.py` (329 lines) |
| `detect_reader` extension | Modified | `src/matchaudit/readers/__init__.py` |
| CLI `--ocr` flags | Modified | `src/matchaudit/cli.py` |
| Optional dependency `[ocr]` | Modified | `pyproject.toml` |
| Synthetic fixture | New | `tests/fixtures/gen_capture_fixture.py` |
| Synthetic capture image | New | `tests/fixtures/sample-capture.png` |
| Unit tests | New | `tests/test_ocr_reader.py` |
| Integration tests (detect_reader) | Modified | `tests/test_readers.py` |
| CLI tests | Modified | `tests/test_cli.py` |

### Key Features

- **Lazy EasyOCR singleton**: Model loads on first `read()` call, cached for subsequent reads
- **Row grouping**: Y-centre clustering with configurable tolerance
- **Header auto-detection**: Heuristic based on alphabetic cell ratio (>40%)
- **Configurable threshold**: `conf_threshold`, `row_tolerance`, `header_rows`, `allowlist`
- **Graceful degradation**: Works without EasyOCR installed (tests pass, CLI shows helpful error)
- **CLI flags**: `--ocr`, `--ocr-language`, `--ocr-conf-threshold`

## Files Changed

```
A  src/matchaudit/readers/ocr.py           (329 lines)
M  src/matchaudit/readers/__init__.py       (+15 lines: lazy registration + image error)
M  src/matchaudit/cli.py                    (+35 lines: --ocr, --ocr-language, --ocr-conf-threshold)
M  pyproject.toml                           (+4 lines: optional-dependencies ocr)
A  tests/fixtures/gen_capture_fixture.py    (Pillow script for synthetic capture)
A  tests/fixtures/sample-capture.png        (5 rows × 4 columns synthetic table)
A  tests/test_ocr_reader.py                 (Unit tests for OcrReader and helpers)
M  tests/test_readers.py                    (+ tests for detect_reader with images)
M  tests/test_cli.py                        (+ tests for --ocr flag)
```

## Test Results

| Metric | Value |
|--------|-------|
| **Total tests** | 94 collected |
| **Passed** | 87 |
| **Skipped** | 7 (TestOcrReaderWithEasyOCR — requires easyocr installed) |
| **Failed** | 0 |
| **Lint (ruff)** | 0 errors |
| **Compliance** | 23/23 scenarios (100%) |
| **Tasks** | 15/15 complete |

The 7 skipped tests are intentional — they verify the end-to-end OCR pipeline with real EasyOCR and require `pip install matchaudit[ocr]`.

## Artifact Inventory

| Artifact | Status | Notes |
|----------|--------|-------|
| `proposal.md` | ✅ Present | Written during sdd-propose |
| `exploration.md` | ✅ Present | Written during sdd-explore |
| `spec.md` | ✅ Created at archive time | Reconstructed from implementation + verify-report; synced to `openspec/specs/readers/spec.md` |
| `design.md` | ✅ Created at archive time | Reconstructed from code analysis; 8 ADRs documented |
| `tasks.md` | ✅ Present | 15/15 tasks marked complete |
| `verify-report.md` | ✅ Present | PASS verdict, 0 blockers, 0 critical |

> **Note**: `spec.md` and `design.md` did not exist before archive. They were created during archive per explicit orchestrator instruction to close the SDD cycle with full artifact coverage. The verify-report had flagged this as a WARNING and SUGGESTION.

## Recommendations

### Short-term
1. **Install EasyOCR and run integration tests**: `pip install matchaudit[ocr] && pytest tests/test_ocr_reader.py::TestOcrReaderWithEasyOCR -v` — validates the full OCR pipeline against the synthetic fixture
2. **Test with real captures**: Run `matchaudit compare --source real_data.csv --captured screenshot.png --ocr --key-columns id` with actual audit screenshots to validate OCR accuracy in production-like conditions

### Medium-term
3. **Performance benchmark**: Measure `OcrReader.read()` latency on real captures (especially first call with model loading). Consider background pre-loading if latency is a UX concern
4. **OpenCV preprocessing**: If OCR accuracy on real captures is below 80%, add image preprocessing (deskew, contrast enhancement, thresholding) before EasyOCR
5. **Update `openspec/config.yaml`**: The config still says "not yet implemented" and "no test runner available" — stale metadata from project initialization

### Long-term
6. **Multi-language OCR**: Enable `--ocr-language` for non-English audit contexts
7. **PDF support**: Extend reader to handle scanned PDFs (requires PDF rasterization before OCR)
