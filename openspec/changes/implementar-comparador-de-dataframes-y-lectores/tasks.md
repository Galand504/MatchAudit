# Tasks: Implementar comparador de dataframes y lectores

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 500–650 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | force-chained |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Models + Readers (foundation) | PR 1 → feature/tracker | `pytest tests/test_readers.py -v` | `python -m matchaudit compare sample.csv sample.csv` | `git revert HEAD` — new files only |
| 2 | ControlPoint + Comparator (core) | PR 2 → PR 1 branch | `pytest tests/test_comparator.py -v` | `python -m matchaudit compare sample.csv misaligned.csv` | `git revert HEAD` on branch |
| 3 | Output + CLI wiring (integration) | PR 3 → PR 2 branch | `pytest tests/test_output.py tests/test_cli.py -v` | `python -m matchaudit compare sample.csv misaligned.csv --output json` | `git revert HEAD` on branch |

## Phase 1: Models

- [x] 1.1 Create `src/matchaudit/core/models.py` — `ControlPoint`, `ComparisonResult`, `RowDiff`, `RowShift`, `ComparisonStats` dataclasses with typing

## Phase 2: Readers

- [x] 2.1 Update `src/matchaudit/readers/__init__.py` — `DataReader` ABC with `read()` and `supports()`; `detect_reader()` factory
- [x] 2.2 Create `src/matchaudit/readers/excel.py` — `ExcelReader` using `pd.read_excel(engine="openpyxl")`
- [x] 2.3 Create `src/matchaudit/readers/csv.py` — `CsvReader` using `pd.read_csv()` with UTF-8 BOM handling

## Phase 3: ControlPoint & Comparator

- [x] 3.1 Create `src/matchaudit/core/control_point.py` — `ControlPoint.extract()` slice by label range, validate key uniqueness
- [x] 3.2 Create `src/matchaudit/core/comparator.py` — `pd.merge(how="outer", indicator=True)` for row classification + column-by-column diff on matched rows + `ComparisonStats` aggregation

## Phase 4: Output & CLI

- [x] 4.1 Update `src/matchaudit/output/__init__.py` — expose `render_comparison()` and formatters
- [x] 4.2 Create `src/matchaudit/output/console.py` — Rich Panel (summary) + Table (diffs), TTY detection, `--output json` plumbing
- [x] 4.3 Modify `src/matchaudit/cli.py` — rewrite `compare` command: `--source`, `--captured`, `--label-column`, `--start`, `--end`, `--key-columns`, `--output` flags; orchestrate detect → read → slice → compare → render

## Phase 5: Tests & Fixtures

- [x] 5.1 Create `tests/fixtures/sample.xlsx` — Excel fixture matching existing `sample.csv`
- [x] 5.2 Create `tests/fixtures/misaligned.csv` — known diffs: missing row, extra row, changed cell value
- [x] 5.3 Create `tests/test_readers.py` — test `read()`, `supports()`, auto-detect by extension, missing-file error
- [x] 5.4 Create `tests/test_comparator.py` — test identical/match/mismatch/missing/extra/shifted/empty/duplicate-key
- [x] 5.5 Create `tests/test_output.py` — test summary panel text, diff table rendering, TTY fallback
