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

### Added

- **`batch-compare` `--prefix-match`**: match one source against multiple captures
  whose stem starts with `<source_stem>_`.  E.g. `usuarios.csv` is compared against
  both `usuarios_primer.png` and `usuarios_ultimo.png`.
- **`codigo_usuario`** added to auto-detected key column candidates.
- **`matchaudit-gui`** — desktop GUI with CustomTkinter (``pip install matchaudit[gui]``).
  Select source + capture via file dialogs, auto-detect key column, run comparison
  with progress indicator, view results in tabbed panels (differences / missing /
  extra), and export to JSON.
- **Portable build**: ``scripts/MatchAudit.spec`` + ``scripts/build.bat`` /
  ``scripts/build.sh`` — build a standalone executable folder with
  PyInstaller that requires zero Python installation to run.

### Fixed

- **False cross-product merge when key column contains NaN**: `astype(str)` was
  converting NaN to the literal string `"nan"`, causing `pd.merge` to match every
  NaN-key row in the source against every NaN-key row in the captured dataset.
  This produced wildly inflated match rates (e.g. 300%) when comparing unrelated
  files that happened to share a column name.

  Fix: NaN-key rows are now filtered out before the merge, then reported
  explicitly as unmatched (missing / extra) with the message `"(key is empty)"`.

- **OCR cell assignment to wrong column**: `min()` with `float("inf")` fallback
  returned the first column when no column boundary contained the cell (e.g. cells
  from "factor de impacto" or "acciones" columns were assigned to "nombre").
  Fix: filter candidate columns to those whose X-range actually contains the cell
  before applying `min()`.  Also moved the empty-string guard to run after
  `_postprocess_text` so OCR artifacts like `'@'` (action buttons) don't become
  empty-string assignments.

- **OCR footer detection too aggressive**: `"of " in v.lower()` matched legitimate
  journal names like "Journal of Latin American Studies".  Fix: strict regex
  pattern (`^showing|rows per page|page \\d+ of|\\d+-\\d+ of`).

- **Duplicate rows in OCR output**: the same journal name appeared twice when a
  ghost read from the action buttons area matched the same data row a second time.
  Fix: skip records identical to the last appended record.
