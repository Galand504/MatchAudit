# Exploration: Implementar comparador de dataframes y lectores

## Current State

### CLI structure
`src/matchaudit/cli.py` defines two Click stubs (`validate` and `compare`) that only print `"not yet implemented"`. The project has package scaffolding (`core/`, `readers/`, `output/`) with empty `__init__.py` files — zero domain logic.

### Test infrastructure
`tests/test_cli.py` has 6 smoke tests covering `--help`, `--version`, `validate`, `compare`, and invalid args — all passing. `tests/conftest.py` provides a `CliRunner` fixture and a `fixtures_dir` pointer. `tests/fixtures/sample.csv` exists with 5 rows of test data (id, name, amount, date).

### Dependencies (from pyproject.toml)
- **click** ≥ 8.1 — CLI framework (already in use)
- **pandas** ≥ 2.1 — dataframe engine (core dependency for the comparator)
- **openpyxl** ≥ 3.1 — Excel reading
- **sqlalchemy** ≥ 2.0 — SQL connections (future use)
- **rich** ≥ 13.7 — terminal formatting (key for output)

### Archive context
The archived proposal (`definir-stack-tecnologico-y-setup-inicial`) established the Python CLI stack and recommended:
- `core/` contains **pure domain logic** with no I/O — comparator, models, control_point
- `readers/` are **I/O adapters** — Excel, CSV, SQL
- `output/` are **presentation adapters** — console, JSON, HTML
- Tests mirror `src/` layout (one test file per source file)
- CLI is thin — only parsing + orchestration, zero business logic

### Files currently absent from working tree
The source files exist only in git feature branches (`feat/definir-stack-y-setup-*`), not on `main`. The egg-info confirms the package was installed at some point but the `.py` files are currently absent from the working directory.

---

## Domain Model

### Control Point
A **control point** represents a subset of records from a source dataset that must be verified. It's the fundamental unit of validation.

```python
@dataclass
class ControlPoint:
    """A named window into a source dataset that must be verified."""
    name: str                         # e.g. "Bloque inicial"
    source: DataFrame                 # The full source dataset
    label_column: str                 # Column used for ordering (e.g. "id")
    start_label: Any                  # First record label (inclusive)
    end_label: Any                    # Last record label (inclusive)
    description: str = ""             # Optional human-readable context
```

Key behavior:
- Extracts a slice of `source` between `start_label` and `end_label` in `label_column` order
- This extracted slice is the **expected subset** — what the screenshot claim to show
- The user provides a **captured file** (Excel/CSV) representing the actual data shown

### Comparison Result
The output of comparing a control point's expected subset against a captured file:

```python
@dataclass
class ComparisonResult:
    status: Literal["match", "mismatch", "error"]
    matched_rows: int
    mismatched_rows: list[RowDiff]
    missing_rows: list[RowDiff]       # In expected but not in captured
    extra_rows: list[RowDiff]         # In captured but not in expected
    shifted_rows: list[RowShift]      # Records present in both but at wrong position
    stats: ComparisonStats

@dataclass
class RowDiff:
    index: int                        # Row position in the source
    key: Any                          # Label value (e.g. id = 42)
    column: str | None                # Which column differs (None = whole row missing)
    expected: Any                     # Value in the expected data
    actual: Any                       # Value in the captured data

@dataclass
class RowShift:
    expected_position: int
    actual_position: int
    key: Any
    surrounding_rows: tuple[Any, Any] # For context

@dataclass
class ComparisonStats:
    total_expected: int
    total_captured: int
    match_rate: float                 # 0.0 to 1.0
    has_misalignment: bool
    severity: Literal["ok", "warning", "critical"]
```

### Output Format
The primary output is a **Rich-rendered console report** with:
1. **Summary header** — colored banner: ✅ MATCH (green) or ❌ MISMATCH (red), plus match rate
2. **Stats table** — total expected, total captured, matched, mismatched, missing, extra
3. **Diff table** — per-row breakdown showing key, column, expected vs actual (only when there are differences)
4. **Alignment section** — if shifts detected, show expected vs actual positions

---

## Approaches

### Comparator Approach

#### 1A. Pandas merge with indicator (RECOMMENDED)
Use `pd.merge(how="outer", indicator=True)` to classify every row as `both`, `left_only`, or `right_only`. Then use `df.compare()` for cell-level diffs on matched rows.

```python
merged = pd.merge(expected, captured, on=key_columns, how="outer", indicator=True, suffixes=("_expected", "_actual"))
```

- **Pros**: — Single merge classifies all rows in one pass; battle-tested pandas pattern; handles multi-key joins naturally; execution plan is vectorized (fast)
- **Cons**: — `compare()` only works on aligned indices (need to filter `both` rows first); column renaming via suffixes can get verbose
- **Effort**: Low

#### 1B. Row-by-row iteration
Loop over expected rows and look up each key in captured.

- **Pros**: — Easy to reason about; full control over comparison logic
- **Cons**: — O(n²) worst case; destroys pandas vectorization; 1000x slower on 50k rows; more code, more bugs
- **Effort**: Medium (simple to write, hard to make performant)
- **Verdict: DO NOT USE**

#### 1C. pandas.merge + custom diff function
Use merge to align rows, then iterate only the matched subset to produce detailed cell-level diffs with context (instead of bare `compare()`).

- **Pros**: — Combines merge efficiency with readable diff output; can annotate each diff with "expected vs actual" as a human-readable sentence
- **Cons**: — Slightly more code than pure pandas; need to handle NaN/None carefully
- **Effort**: Low-Medium

**Recommendation: 1A (merge with indicator) as primary, with 1C's custom diff logic for cell-level detail.** The merge + indicator classifies rows. Then for `both` rows, use `df.compare()` OR a custom column-by-column comparison (depending on desired output verbosity).

---

### Reader Approach

#### 2A. Pandas-based reader (RECOMMENDED)
Use `pd.read_excel()` and `pd.read_csv()` with a thin wrapper class.

```python
class ExcelReader:
    def read(self, path: Path, sheet: str = 0, **kwargs) -> DataFrame:
        return pd.read_excel(path, sheet_name=sheet, engine="openpyxl", **kwargs)

class CsvReader:
    def read(self, path: Path, **kwargs) -> DataFrame:
        return pd.read_csv(path, **kwargs)
```

- **Pros**: — 0 additional dependencies (openpyxl already installed); pandas handles type inference, date parsing, missing values, encodings; well-documented edge cases; consistent `DataFrame` output regardless of input format
- **Cons**: — `pd.read_excel()` is slower than raw openpyxl on huge files (~0.5s vs ~0.05s for small files, but still sub-second); limited control over cell-level formatting
- **Effort**: Low

#### 2B. Raw openpyxl + csv stdlib
Use openpyxl directly for Excel and `csv.DictReader` for CSV.

- **Pros**: — Full control over cell reading (merged cells, styles, formulas); no pandas overhead for reading
- **Cons**: — Must manually construct DataFrames from raw cells; lose pandas type inference; more code per reader; csv stdlib doesn't handle encoding/quoting edge cases as well
- **Effort**: Medium

**Recommendation: 2A (pandas-based).** The consistency of getting a `DataFrame` from every reader is more valuable than the marginal speed gain of raw openpyxl. If Excel files >100k rows become a bottleneck, introduce `calamine` (Rust-based) later without changing the interface.

---

### Reader Interface

```python
# readers/__init__.py
from abc import ABC, abstractmethod
from pathlib import Path
from pandas import DataFrame

class DataReader(ABC):
    """Interface for all data source readers."""

    @abstractmethod
    def read(self, path: Path, **kwargs) -> DataFrame:
        """Read a data source and return a DataFrame."""
        ...

    @abstractmethod
    def supports(self, path: Path) -> bool:
        """Return True if this reader can handle the given path."""
        ...
```

This allows the CLI command to auto-detect reader based on extension:
```python
READERS: list[DataReader] = [ExcelReader(), CsvReader()]

def detect_reader(path: Path) -> DataReader:
    for reader in READERS:
        if reader.supports(path):
            return reader
    raise ValueError(f"No reader found for {path}")
```

---

### Output Approach

#### 3A. Rich Tables with Panel (RECOMMENDED)
Use `rich.table.Table` for data display and `rich.panel.Panel` for summary blocks.

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def print_summary(stats: ComparisonStats) -> None:
    if stats.has_misalignment:
        panel = Panel(f"[red]❌ MISMATCH[/red]\nMatch rate: {stats.match_rate:.1%}", style="red")
    else:
        panel = Panel(f"[green]✅ MATCH[/green]\nMatch rate: {stats.match_rate:.1%}", style="green")
    console.print(panel)

def print_diff_table(diffs: list[RowDiff]) -> None:
    table = Table(title="Row Differences")
    table.add_column("Row", style="dim")
    table.add_column("Key")
    table.add_column("Column")
    table.add_column("Expected", style="cyan")
    table.add_column("Actual", style="red")
    for d in diffs:
        table.add_row(str(d.index), str(d.key), d.column or "—", str(d.expected), str(d.actual))
    console.print(table)
```

- **Pros**: — Rich is already installed; colored tables are immediately useful; no external rendering dependencies; works in any terminal
- **Cons**: — Not machine-readable (need JSON for that); limited to terminal viewport width
- **Effort**: Low

#### 3B. Export-only (JSON + CSV files)
Skip console rendering entirely and write results to structured files.

- **Pros**: — Simple, scriptable; consumers can diff output files
- **Cons**: — No immediate user feedback; defeats the purpose of an interactive CLI tool for auditors
- **Effort**: Low

#### 3C. Rich + JSON export (RECOMMENDED HYBRID)
Default to Rich console output, with `--output json` or `--output csv` flags for automated use.

- **Pros**: — Best of both worlds
- **Cons**: — Slightly more CLI parameter handling
- **Effort**: Low

**Recommendation: 3C (Rich primary + export capability)**. Console output is the main UX for auditors. JSON/CSV export via `--output` flag prepares for future automation.

---

## Affected Areas

| File | Action | Why |
|------|--------|-----|
| `src/matchaudit/core/models.py` | **Create** | Domain dataclasses: `ControlPoint`, `ComparisonResult`, `RowDiff`, `ComparisonStats` |
| `src/matchaudit/core/comparator.py` | **Create** | Core comparison engine — merge + indicator + cell-level diff |
| `src/matchaudit/core/control_point.py` | **Create** | Control point creation and slice extraction |
| `src/matchaudit/readers/__init__.py` | **Update** | `DataReader` abstract base class |
| `src/matchaudit/readers/excel.py` | **Create** | `ExcelReader` — pandas-based (openpyxl engine) |
| `src/matchaudit/readers/csv.py` | **Create** | `CsvReader` — pandas-based |
| `src/matchaudit/output/__init__.py` | **Update** | Expose formatter functions |
| `src/matchaudit/output/console.py` | **Create** | Rich-based report rendering |
| `src/matchaudit/output/json.py` | **Create** | JSON export (future) |
| `src/matchaudit/cli.py` | **Modify** | Wire `compare` command to comparator + readers + output |
| `tests/test_comparator.py` | **Create** | Unit tests for comparator with known diffs |
| `tests/test_readers.py` | **Create** | Unit tests for Excel/CSV readers |
| `tests/test_output.py` | **Create** | Unit tests for console rendering |
| `tests/fixtures/sample.xlsx` | **Create** | Excel test data for reader tests |
| `tests/fixtures/misaligned.csv` | **Create** | CSV with known differences for comparison tests |
| `openspec/changes/implementar-comparador-de-dataframes-y-lectores/state.yaml` | **Create** | SDD state tracking |

---

## Recommendation

### Comparator: Pandas merge with indicator (Approach 1A + 1C hybrid)
- Use `pd.merge(how="outer", indicator=True)` for row classification
- Use custom column-by-column comparison on matched rows (not bare `compare()`)
- This gives accurate row classification + readable cell-level diffs in one pass

### Readers: Pandas-based wrappers (Approach 2A)
- Thin factory pattern (`detect_reader` by extension)
- `pd.read_excel(engine="openpyxl")` and `pd.read_csv()` with standard kwargs
- Interface: `DataReader` ABC with `read()` and `supports()` methods

### Output: Rich console + --output flag (Approach 3C)
- Summary panel: colored MATCH/MISMATCH + match rate
- Diff table: per-row breakdown with expected vs actual
- `--output json` / `--output csv` for machine-readable export (plumb in this change, implement in next)

### Architecture flow
```
CLI (compare command)
  → detect_reader(source_path) → reader.read()
  → detect_reader(captured_path) → reader.read()
  → ControlPoint.extract(source_df, label_column, start, end)
  → Comparator.compare(expected_df, captured_df, key_columns)
  → ConsoleFormatter.report(comparison_result)
```

### Order of implementation
1. **Models** (`models.py`) — dataclasses, no dependencies beyond stdlib and typing
2. **Readers** (`excel.py`, `csv.py`) — load DataFrames from files
3. **ControlPoint** (`control_point.py`) — slice extraction
4. **Comparator** (`comparator.py`) — core comparison engine
5. **Output** (`console.py`) — Rich report rendering
6. **CLI wiring** — connect `compare` command to the pipeline
7. **Tests** — one file per module, fixtures with known differences

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Source files absent from working tree** — `.py` files exist only in git feature branches, not on `main`. The working directory has only `.pyc` caches and `egg-info` | **High** | The orchestrator must ensure files are restored (e.g. checkout from feature branch or merge to main) before this change is applied. Otherwise, the `sdd-apply` phase will fail because source files don't exist |
| **Pandas `merge` behavior with duplicate keys** — if key columns aren't unique, `merge` produces a Cartesian product of matches, exploding row counts silently | **Medium** | Document as a precondition: key columns MUST be unique in both datasets. Add validation at the `ControlPoint` level with `df.duplicated().any()` check, returning a clear error |
| **Excel type inference differences** — pandas may read numbers as strings or dates inconsistently depending on cell formatting | **Medium** | Add a normalization step in the comparator: cast shared columns to consistent dtypes before comparing. MatchAudit already controls both inputs, so this is manageable |
| **Rich output in non-TTY environments** — if output is piped or redirected, Rich may render raw ANSI codes or fail | **Low** | Use `Console(force_terminal=False)` or detect TTY via `Console.is_terminal`. Fall back to plain text if not a TTY |
| **CSV encoding issues** — users may provide CSV files in Latin-1, UTF-16, or other encodings | **Low** | Default to UTF-8 with `encoding="utf-8-sig"` (handles BOM); add `--encoding` flag as optional CLI param for edge cases |
| **Review workload** — comparator + readers + output is a substantial change (~300-500 lines across 7+ new files) | **Medium** | Implementation can be split: (1) readers first, (2) comparator + models, (3) output + CLI wiring. Three small PRs vs one large one |

---

## Ready for Proposal

**Yes.** The domain model, comparator strategy, reader architecture, and output format are well-defined. The exploration confirms:

1. **Comparator**: Pandas `merge` with `indicator=True` is the correct approach — vectorized, robust, single-pass
2. **Readers**: Pandas-based wrappers behind a common `DataReader` interface — zero new dependencies
3. **Output**: Rich console tables as primary UX, with `--output` flag for future JSON/CSV export
4. **Architecture**: Clean separation (models → readers → control point → comparator → output) follows the established `core/` / `readers` / `output` convention

The orchestrator should proceed to `sdd-propose` with the caveat that the source files must be restored to the working tree first (they currently exist only in git feature branches).

**Orchestrator note**: Before `sdd-apply`, ensure the source files from feature branch `feat/definir-stack-y-setup-01-foundation` are merged to `main` or checked out — currently `main` only has `.gitignore`.
