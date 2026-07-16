# Tasks: Definir stack tecnológico y setup inicial

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~180–250 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR (small change, force-chained by user decision) |
| Delivery strategy | force-chained |
| Chain strategy | feature-branch-chain |

```
Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: feature-branch-chain
400-line budget risk: Low
```

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Git init + config + package skeleton + CLI entry | PR #1 (base: feature/tracker) | `uv run matchaudit --help` | `uv run matchaudit --help` confirms CLI works | `rm -rf .git src/ pyproject.toml` |
| 2 | Test infra + CI pipeline | PR #2 (base: PR #1 branch) | `uv run pytest -x` | N/A — CI validates on push | `rm -rf tests/ .github/` |

## Phase 1: Foundation

- [x] 1.1 Init git repo: `git init` + first commit with `.gitignore` (Python + uv + IDE)
- [x] 1.2 Create `pyproject.toml` with uv: metadata, deps (click, pandas, openpyxl, sqlalchemy, rich), tool configs (ruff, pytest)
- [x] 1.3 Write `README.md` (quick start, uv install, usage) + `LICENSE` (MIT)
- [x] 1.4 Run `uv sync` to install deps and generate `uv.lock`

## Phase 2: Package Skeleton + CLI

- [x] 2.1 Create `src/matchaudit/__init__.py`, `__main__.py` (`python -m matchaudit`)
- [x] 2.2 Create `src/matchaudit/cli.py` with Click root command (`--help` functional)
- [x] 2.3 Create stub directories: `core/`, `readers/`, `output/` with `__init__.py`
- [x] 2.4 Add `[project.scripts]` entry point in `pyproject.toml` for `matchaudit` CLI

## Phase 3: Test Infrastructure

- [x] 3.1 Create `tests/conftest.py` with shared pytest fixtures
- [x] 3.2 Create `tests/test_cli.py` with Click CliRunner smoke test
- [x] 3.3 Create `tests/fixtures/sample.csv` placeholder test data file

## Phase 4: CI Pipeline

- [x] 4.1 Create `.github/workflows/ci.yml`: pytest + ruff check on push/PR (3.11, 3.12)

## Phase 5: Verification

- [x] 5.1 Run `uv run pytest -x` — all tests pass
- [x] 5.2 Run `ruff check src/` — 0 errors
- [x] 5.3 Run `uv run matchaudit --help` — CLI help displayed
