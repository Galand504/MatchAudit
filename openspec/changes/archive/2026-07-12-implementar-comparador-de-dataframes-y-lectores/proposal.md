# Proposal: Implementar comparador de dataframes y lectores

## Intent

MatchAudit tiene CLI stubs pero cero lógica de dominio. Sin motor de comparación, la herramienta no produce valor. Este cambio implementa el núcleo: lectores que cargan datos desde Excel/CSV, un comparador que detecta diferencias fila a fila y celda a celda, y un formateador que presenta resultados en consola.

## Scope

### In Scope
- Modelos de dominio: `ControlPoint`, `ComparisonResult`, `RowDiff`, `RowShift`, `ComparisonStats`
- Lectores pandas-based con interfaz `DataReader` — Excel (openpyxl) y CSV, auto-detección por extensión
- Comparador: `pd.merge(how="outer", indicator=True)` + diff columna por columna en filas coincidentes
- Control point: extracción de slice por rango de etiquetas (fila + columna clave)
- Output: Rich console con summary panel + diff table; flag `--output json` plumbed
- Tests unitarios por módulo + fixtures con diferencias conocidas

### Out of Scope
- Output JSON/CSV completo (solo plumbing de flag)
- Lector SQL, multi-sheet, o formatos adicionales (calamine, parquet)
- UI web, dashboard, o pre-commit hooks

## Capabilities

### New Capabilities
- `data-comparison`: Motor de comparación — merge con indicador, diff celda a celda, clasificación de filas (match/missing/extra/shifted), estadísticas de accuracy
- `data-reading`: Lectores via interfaz `DataReader` — soporte Excel (openpyxl) y CSV, auto-detección por extensión
- `output-formatting`: Formateo de resultados — Rich console tables/panels, preparación para exportación JSON

### Modified Capabilities
None — no existen specs previas.

## Approach

1. **Models** (`models.py`) — dataclasses puras sin I/O
2. **Readers** (`excel.py`, `csv.py`) — `DataReader` ABC + `detect_reader()` factory
3. **ControlPoint** (`control_point.py`) — slice extraction por label range
4. **Comparator** (`comparator.py`) — merge outer con indicator, luego diff columna por columna en matched rows
5. **Output** (`console.py`) — Rich Panel (summary) + Table (diffs), `--output json` flag
6. **CLI wiring** — comando `compare` orquesta: detect → read → slice → compare → format
7. **Tests** — uno por módulo, fixtures con datos conocidos

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/matchaudit/core/models.py` | New | Domain dataclasses |
| `src/matchaudit/core/comparator.py` | New | Merge + diff engine |
| `src/matchaudit/core/control_point.py` | New | Slice extraction |
| `src/matchaudit/readers/__init__.py` | Modified | `DataReader` ABC |
| `src/matchaudit/readers/excel.py` | New | Pandas + openpyxl |
| `src/matchaudit/readers/csv.py` | New | Pandas CSV |
| `src/matchaudit/output/__init__.py` | Modified | Export formatters |
| `src/matchaudit/output/console.py` | New | Rich report rendering |
| `src/matchaudit/cli.py` | Modified | Wire `compare` command |
| `tests/` | New | Tests + fixtures |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Source files ausentes del working tree | High | Checkout feat branch o merge a main antes de apply |
| Duplicate keys → Cartesian explosion en merge | Medium | Validar unicidad pre-merge con `df.duplicated()` |
| Type inference differences Excel vs CSV | Medium | Normalizar dtypes de columnas compartidas pre-comparación |
| Rich ANSI en piped output | Low | Detectar TTY, fallback a texto plano |

## Rollback Plan

`git revert` del/los commits del cambio. Si es PR separado, cerrar sin merge. Los archivos nuevos se eliminan al revertir; `cli.py` vuelve a stubs.

## Dependencies

- pandas ≥ 2.1, openpyxl ≥ 3.1, rich ≥ 13.7 (ya en `pyproject.toml`)
- Source files de `src/matchaudit/` presentes en working tree

## Success Criteria

- [ ] `pytest tests/` pasa — tests nuevos + existentes
- [ ] `ruff check src/` — 0 errores
- [ ] `matchaudit compare --help` muestra parámetros esperados
- [ ] `matchaudit compare data.csv data.csv` reporta 0 diferencias (archivo vs sí mismo)
- [ ] `matchaudit compare data.csv misaligned.csv` detecta diferencias conocidas
