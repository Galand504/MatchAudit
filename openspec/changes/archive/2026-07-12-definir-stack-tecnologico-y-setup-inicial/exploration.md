# Exploration: Definir stack tecnológico y setup inicial

## Current State

Project is at conceptual stage only. The repository contains a single `MatchAudit.md` definition file, an empty `openspec/` directory (with config.yaml and no specs), and no code, no dependencies, no test runner, no git history, no build system, and no CI.

The project root is a local clone of the repository. No `.git` directory exists at the time of this exploration.

## Product Requirements Snapshot

Based on `MatchAudit.md`, the tool MUST:

1. **Import data sources** — read Excel (.xlsx) and CSV files; optionally connect to SQL databases
2. **Define control points** — let the user select record subsets to verify (e.g. rows 1–40, rows 100–140)
3. **Validate automatically** — compare control-point data against the full source dataset
4. **Detect misalignments** — identify missing, shifted, or incorrect records with exact location
5. **Report differences** — show which rows differ and what the discrepancy is
6. **Be accessible to analysts** — not require complex tooling or data-modeling knowledge

The core operation is **dataframe comparison**: take a reference dataset (full source), take a sample (control point), and check that the sample is a correct subset of the reference. This is fundamentally a tabular data problem, not a visual/image problem.

## Tool Type Analysis

| Type | Fit | Why |
|------|-----|-----|
| **CLI tool** | ✅ Best | Natural for data pipelines, scriptable, minimal UI overhead, fits analyst workflows (can be chained with other tools) |
| Desktop app | ❌ Overkill | Electron/Tauri adds 10–50 MB for what is fundamentally a batch data processor |
| Web app | ❌ Premature | Requires server, auth, deployment — unneeded for v1; can be added later if needed |
| Library/API | 🟡 Possible | Could be distributed as a Python library, but the primary use case is interactive validation, not integration |

**Recommendation: CLI as primary interface.** Users run it on their machine with data files. No server, no cloud, no deployment.

## Stack Options Compared

### Option A: Python CLI (Recommended)
| Aspect | Detail |
|--------|--------|
| **Language** | Python 3.11+ |
| **Package mgmt** | `uv` (fast, modern; Astral) or Poetry |
| **Entry point** | `matchaudit` CLI via `pyproject.toml` `[project.scripts]` |
| **CLI framework** | Click or Typer (Click is battle-tested; Typer adds auto-docs) |
| **Data handling** | **Pandas** for dataframe operations, **openpyxl** for .xlsx, **csv** stdlib, **SQLAlchemy** for SQL connections |
| **Validation core** | Pure Pandas (`.equals()`, `.compare()`, `merge()` with indicators) |
| **Testing** | pytest + pytest-cov |
| **Code quality** | ruff (linter + formatter), mypy (optional strict mode) |
| **Diff output** | Rich (terminal formatting) + JSON/CSV export |
| **Pros** | — Dataframes are the natural abstraction for this problem<br/>— Pandas is the de facto standard for tabular data in Python<br/>— openpyxl handles .xlsx without external dependencies<br/>— pytest ecosystem is mature and reliable<br/>— Analysts/auditors can read and extend Python<br/>— Fast to prototype (no compilation, no build step)<br/>— Rich library ecosystem for SQL, Excel, CSV out of the box |
| **Cons** | — Python runtime required on user machine (mitigation: PyInstaller or shiv for standalone binary)<br/>— Pandas memory usage on very large datasets (millions of rows) |
| **Effort** | **Low** — standard Python project setup, well-worn path |

### Option B: Python + Streamlit Web UI
| Aspect | Detail |
|--------|--------|
| **Language** | Python 3.11+ |
| **Framework** | Streamlit on top of the same core Python logic |
| **Data handling** | Same: Pandas + openpyxl + SQLAlchemy |
| **Testing** | Same: pytest |
| **Pros** | — Web UI without JS/frontend complexity<br/>— Easy file upload via browser<br/>— Richer output rendering (tables, highlights) |
| **Cons** | — Requires server process (`streamlit run`), not just a CLI command<br/>— Streamlit adds ~30 dependencies and can feel sluggish<br/>— Over-engineered for v1: auditors don't need a web browser to validate CSV files<br/>— Deployment and sharing friction |
| **Effort** | **Medium** — more moving parts, not justified for v1 |

### Option C: TypeScript / Node.js CLI
| Aspect | Detail |
|--------|--------|
| **Language** | TypeScript 5.x |
| **Runtime** | Node.js 22 LTS |
| **CLI framework** | Commander + inquirer |
| **Data handling** | `xlsx` (SheetJS) for .xlsx, `papaparse` for CSV |
| **Testing** | Vitest |
| **Code quality** | biome (linter + formatter) or ESLint + Prettier |
| **Pros** | — Single language ecosystem<br/>— TypeScript gives static typing natively<br/>— Fast startup (no Python startup overhead) |
| **Cons** | — **No dataframe library** — would need to implement merge/compare manually or pull in a JS dataframe lib (Danfo.js, Arquero) which are immature compared to Pandas<br/>— SheetJS community edition has limitations (no xlsx writing without paid license for some features)<br/>— Less natural fit for data reconciliation work<br/>— Analysts are less likely to contribute to or extend a Node.js codebase<br/>— Testing data pipelines in JS is more ceremony |
| **Effort** | **Medium-High** — reimplementing what Pandas gives for free |

## Recommendation: Option A — Python CLI

**Python + Pandas + Click + pytest + uv + ruff** is the right stack for MatchAudit v1.

### Why Python wins for this problem

The core operation of MatchAudit is **dataframe comparison** — taking two tabular datasets and finding their differences. Pandas was designed for exactly this. In ~10 lines of Python you can load two Excel files, align them by key columns, and produce a diff report. In any other stack, you'd be reimplementing `merge`, `compare`, or writing row-by-row iteration logic.

### Specific package breakdown

| Concern | Package | Rationale |
|---------|---------|-----------|
| **Package manager** | `uv` | ~10–100x faster than pip, single binary, lockfile, virtualenv management. Astral's uv is the modern standard. |
| **CLI framework** | `click` | Mature, well-documented, composable commands. Typer is also good but adds FastAPI-style auto-docs that we don't need yet. |
| **Dataframes** | `pandas` | Industry standard for tabular data in Python. For very large datasets, can later introduce `polars` as an opt-in engine. |
| **Excel reading/writing** | `openpyxl` | Native .xlsx support, no external dependencies. Handles formatting, sheets, cell ranges. |
| **SQL connections** | `sqlalchemy` | Industry standard ORM/connection layer. Supports PostgreSQL, MySQL, SQLite, etc. |
| **Terminal output** | `rich` | Beautiful formatted tables, colored diffs, progress bars. Makes CLI output professional. |
| **Testing** | `pytest` | De facto standard. `pytest-cov` for coverage, `pytest-xdist` for parallel when the suite grows. |
| **Linting/formatting** | `ruff` | Single tool for linting + formatting, extremely fast, pyproject.toml config. |
| **Type checking** | `mypy` (optional) | Gradual typing — start with loose, add strictness as the codebase matures. |

### Python version

**Python 3.11+.** 3.11 introduced significant performance improvements, better exception messages, and `tomllib` in stdlib. It is widely available in Ubuntu 24.04+, RHEL 10+, and via pyenv on any platform.

## Project Structure Suggestion

```
matchaudit/
├── pyproject.toml              # Project metadata, dependencies, tool config
├── README.md                   # Quick start, usage examples
├── LICENSE                     # MIT or Apache 2.0
├── .gitignore
├── .pre-commit-config.yaml     # Lint/format hooks
│
├── src/
│   └── matchaudit/
│       ├── __init__.py
│       ├── __main__.py         # python -m matchaudit entry point
│       ├── cli.py              # Click commands (root + subcommands)
│       ├── core/               # Domain logic — no I/O, pure functions
│       │   ├── __init__.py
│       │   ├── models.py       # pydantic/dataclass models
│       │   ├── control_point.py # Control point definition & validation
│       │   ├── comparator.py   # Data comparison engine
│       │   └── reporter.py     # Diff formatting & report generation
│       ├── readers/            # Data source import adapters
│       │   ├── __init__.py
│       │   ├── excel.py        # openpyxl reader
│       │   ├── csv.py          # stdlib csv reader
│       │   └── sql.py          # SQLAlchemy reader
│       └── output/             # Output formatters
│           ├── __init__.py
│           ├── console.py      # Rich-based terminal output
│           ├── json.py         # JSON report
│           └── html.py         # HTML diff report
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Shared fixtures (sample dataframes)
│   ├── test_control_point.py
│   ├── test_comparator.py
│   ├── test_reporter.py
│   ├── test_cli.py             # Click CliRunner tests
│   └── fixtures/               # Static test data files
│       ├── sample.xlsx
│       ├── sample.csv
│       └── misaligned.xlsx     # File with known differences
│
└── docs/
    └── architecture.md         # Decision records, component diagram
```

### Key architectural decisions embedded in the structure

1. **`src/` layout** — standard Python package layout (`src/matchaudit/`). Avoids import confusion and forces proper packaging.
2. **`core/` contains no I/O** — comparator, models, control_point are pure functions with no file/socket dependencies. This makes them trivially testable.
3. **`readers/` and `output/` are adapters** — they implement interfaces consumed by `core/`. Swapping Excel for Parquet or console for HTML is an adapter change, not a domain change.
4. **CLI is thin** — `cli.py` only parses args, calls core logic, passes results to output. Zero business logic in CLI.
5. **tests mirror `src/` layout** — `test_comparator.py` tests `core/comparator.py`. One test file per source file keeps navigation predictable.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **No git repository** — no version control, no collaboration, no safety net | High | Init git as first non-negotiable step of setup |
| **No CI pipeline** — no automated test execution, no lint checks, no quality gate | Medium | Add GitHub Actions (or equivalent) in setup — even a trivial `pytest` run prevents regressions |
| **Pandas learning curve** — the team may not be fluent in dataframe operations | Low | Use pandas at a straightforward level (load, merge, compare, filter). The `comparator.py` module encapsulates all pandas usage behind a clean API. The rest of the codebase never imports pandas directly. |
| **Large dataset performance** — Excel files with 100k+ rows may strain openpyxl | Medium | openpyxl is read-optimized; stay on it for v1. If needed, introduce `calamine` (Rust-based Python Excel reader) which is 10x faster. |
| **No pre-commit hooks** — formatting/linting can drift without enforcement | Low | Add `pre-commit` with ruff hooks from day one |
| **User needs a different platform** — Python may not be installed on audit-team machines | Medium | Package as standalone binary via `shiv` or `PyInstaller` after v1 stabilizes. Users on Windows can use `pipx install matchaudit` with Python installed. |

## Ready for Proposal

**Yes.** The stack decision is clear — Python CLI with Pandas as the data engine, Click for the CLI, pytest for testing, uv for package management, and ruff for quality. The project structure follows well-established Python packaging conventions with clean separation between domain logic, I/O adapters, and CLI.

The orchestrator should tell the user that this exploration confirms a Python CLI stack is the right fit, and that the next phase (sdd-propose) will formalize the proposal with scope, approach, and rollback plan.
