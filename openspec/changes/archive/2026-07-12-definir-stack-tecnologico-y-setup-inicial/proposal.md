# Proposal: Definir stack tecnológico y setup inicial

## Intent

MatchAudit está en fase conceptual — no hay código, dependencias, git, CI, ni tests. Este cambio establece el scaffold del proyecto Python CLI: inicializa el repo, configura el toolchain (uv, ruff, pytest, mypy opcional), crea la estructura de paquete, y agrega CI básico. El objetivo es que el próximo cambio pueda empezar a implementar lógica de dominio sin fricción de setup.

## Scope

### In Scope
- Inicializar git repo + `.gitignore` + README + LICENSE (MIT)
- `pyproject.toml` con uv: dependencias (click, pandas, openpyxl, sqlalchemy, rich) y tool configs
- Esqueleto `src/matchaudit/` con CLI entry point y estructura de directorios (core/, readers/, output/)
- Esqueleto `tests/` con conftest.py + fixtures/ + tests placeholder
- CI vía GitHub Actions (pytest + ruff check en push/PR)

### Out of Scope
- Implementación de lógica de comparación (siguiente cambio)
- Distribución binaria standalone (shiv/PyInstaller — post-v1)
- Readers concretos (SQL, Excel avanzado)
- Output formatters (HTML, JSON)
- Pre-commit hooks

## Capabilities

### New Capabilities
None — este cambio es setup técnico, no introduce capabilities de producto.

### Modified Capabilities
None — no existen specs previas, el proyecto está vacío.

## Approach

1. `git init` + escribir archivos de configuración (`.gitignore`, `pyproject.toml`, `LICENSE`, `README.md`)
2. `uv sync` para instalar dependencias desde `pyproject.toml`
3. Crear estructura `src/matchaudit/` con `__init__.py`, `__main__.py`, y directorios `core/`, `readers/`, `output/`
4. `cli.py` con Click command stub (`matchaudit --help` funcional)
5. `tests/` con `conftest.py`, test placeholder, y `fixtures/`
6. Configurar ruff + pytest en `pyproject.toml`
7. Crear `.github/workflows/ci.yml` con jobs de test y lint
8. Validar: `uv run pytest`, `ruff check src/`, `uv run matchaudit --help`

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `pyproject.toml` | New | Project metadata, dependencies, tool configs |
| `src/matchaudit/` | New | Package skeleton con CLI entry point |
| `tests/` | New | Test infrastructure con conftest + fixtures |
| `.github/workflows/ci.yml` | New | CI pipeline (pytest + ruff) |
| `.gitignore`, `README.md`, `LICENSE` | New | Project scaffolding files |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| uv no instalado en máquina dev | Medium | Documentar en README: `curl -LsSf https://astral.sh/uv/install.sh | sh` |
| Python version mismatch CI vs local | Low | CI matrix testing 3.11 y 3.12 |
| openpyxl lento con >100k filas | Low | Diferido: reemplazar con calamine si es necesario |

## Rollback Plan

Eliminar el directorio `.git` y todos los archivos creados (revertir a estado pre-cambio). O, si hay commits, `git reset --hard` al commit anterior + limpiar archivos no trackeados.

## Dependencies

- `uv` ≥ 0.4 instalado
- `git` ≥ 2.30 instalado
- Acceso a GitHub para CI

## Success Criteria

- [ ] `uv run pytest` pasa (al menos tests placeholder)
- [ ] `ruff check src/` produce 0 errores
- [ ] `ruff format --check src/` pasa
- [ ] `uv run matchaudit --help` muestra ayuda del CLI
- [ ] GitHub Actions CI pasa en push a main
