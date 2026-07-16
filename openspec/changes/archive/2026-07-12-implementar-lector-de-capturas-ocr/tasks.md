# Tasks: Implementar lector de capturas OCR

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 350-430 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (ocr core) → PR 2 (wiring + CLI) |
| Delivery strategy | force-chained |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Deps + OcrReader core + fixture + unit tests | PR 1 (base: feat/ocr-reader) | `pytest tests/test_ocr_reader.py -v` | `python tests/fixtures/gen_capture_fixture.py && pytest tests/test_ocr_reader.py -v` | `git revert <pr1-sha>` — remove ocr.py, pyproject dep, fixture, tests |
| 2 | Wiring detect_reader + CLI `--ocr` flag | PR 2 (base: PR 1 branch) | `pytest tests/test_readers.py tests/test_cli.py -v` | same command | `git revert <pr2-sha>` — revert __init__.py, cli.py, conftest.py |

## Phase 1: Dependencies & Fixture

- [x] 1.1 Add `[project.optional-dependencies] ocr = ["easyocr"]` to `pyproject.toml`
- [x] 1.2 Create `tests/fixtures/gen_capture_fixture.py` — Pillow script drawing known 5×4 table
- [x] 1.3 Run fixture generator to produce `tests/fixtures/sample-capture.png`

## Phase 2: Core — OcrReader

- [x] 2.1 Create `src/matchaudit/readers/ocr.py` — `OcrReader(DataReader)` with lazy EasyOCR singleton
- [x] 2.2 Implement `_group_by_row()` — Y-center clustering from EasyOCR bboxes
- [x] 2.3 Implement `_detect_header()` + `_build_dataframe()` — header heuristic + DataFrame from groups

## Phase 3: Integration — detect_reader + CLI

- [x] 3.1 Register `OcrReader` in `_ensure_readers()`, extend `detect_reader` error to mention images
- [x] 3.2 Add `sample_capture` fixture to `tests/conftest.py`
- [x] 3.3 Add `--ocr` flag to `compare` in `cli.py`; pass `force_ocr` to bypass `detect_reader`

## Phase 4: Tests

- [x] 4.1 Write `TestOcrReader`: `supports()` for .png/.jpg/.jpeg, `read()` returns DataFrame from fixture, rejects unknown ext
- [x] 4.2 Write edge-case tests: `conf_threshold` filter, `header_rows` override, empty cells (null bbox regions), allowlist restriction
- [x] 4.3 Write `TestDetectReaderOcr` in `test_readers.py`: detects OcrReader for .png/.jpg, unknown ext still raises
- [x] 4.4 Write CLI test in `test_cli.py`: `--ocr` forces OcrReader on .csv; graceful error when EasyOCR missing
