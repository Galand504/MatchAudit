# Changelog

## [Unreleased]

### Added

- **`batch-compare` command**: compare an entire directory of source files against
  corresponding captures matched by filename stem (e.g. `paises.xlsx` ↔ `paises.png`).
  Prints a consolidated summary table with per-file results and detailed panels
  for mismatches. OCR model is loaded once and reused across all images.
  - `--source-dir`: directory with `.csv` / `.xlsx` source files
  - `--captured-dir`: directory with `.csv` / `.xlsx` / `.png` / `.jpg` / `.jpeg` captures
  - Honors `--key-columns`, `--ocr-language`, `--ocr-conf-threshold`, `--ocr-upscale`
  - Warns about files without a matching counterpart on either side

### Fixed

- **False cross-product merge when key column contains NaN**: `astype(str)` was
  converting NaN to the literal string `"nan"`, causing `pd.merge` to match every
  NaN-key row in the source against every NaN-key row in the captured dataset.
  This produced wildly inflated match rates (e.g. 300%) when comparing unrelated
  files that happened to share a column name.

  Fix: NaN-key rows are now filtered out before the merge, then reported
  explicitly as unmatched (missing / extra) with the message `"(key is empty)"`.
