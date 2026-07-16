```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:445a1adcaa31ed4de4e82d79516388c9deafba78d09c655f7c8e7a87cf9dffcc
verdict: pass
blockers: 0
critical_findings: 0
requirements: 10/10
scenarios: 23/23
test_command: uv run pytest tests/ -v --tb=short
test_exit_code: 0
test_output_hash: sha256:445a1adcaa31ed4de4e82d79516388c9deafba78d09c655f7c8e7a87cf9dffcc
build_command: ruff check src/matchaudit/
build_exit_code: 0
build_output_hash: sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18
```

## Verification Report

**Change**: implementar-lector-de-capturas-ocr
**Version**: N/A (spec.md no disponible — requisitos extraídos de proposal.md + tasks.md)
**Mode**: Standard (Strict TDD desactivado)

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 15 |
| Tasks complete | 15 |
| Tasks incomplete | 0 |

### Build & Tests Execution

**Build (ruff lint)**: ✅ Passed
```text
rados@feat/ocr-reader-02-wiring
$ ruff check src/matchaudit/
All checks passed!
```

**Tests (pytest)**: ✅ 87 passed, 7 skipped, 0 failed
```text
$ uv run pytest tests/ -v --tb=short
94 items collected
87 passed, 7 skipped in 1.63s
```
7 skipped = `TestOcrReaderWithEasyOCR` — correcto: EasyOCR no está instalado (graceful degradation).

**Coverage**: ➖ No se ha ejecutado cobertura (no está configurada en pyproject.toml).

### Spec Compliance Matrix

Requisitos extraídos del `proposal.md` (Success Criteria) + `tasks.md` (detalle de implementación).
No se encontraron `spec.md` ni `design.md` — ver Issues.

| # | Requisito | Escenario | Test | Resultado |
|---|-----------|-----------|------|-----------|
| R1 | OcrReader implementa DataReader | Instancia válida | `test_readers.py::test_reader_implements_abc` | ✅ COMPLIANT |
| R2 | supports() para .png | Extensiones soportadas | `test_ocr_reader.py::test_supports_png` | ✅ COMPLIANT |
| R2 | supports() para .jpg | Extensiones soportadas | `test_ocr_reader.py::test_supports_jpg` | ✅ COMPLIANT |
| R2 | supports() para .jpeg | Extensiones soportadas | `test_ocr_reader.py::test_supports_jpeg` | ✅ COMPLIANT |
| R2 | supports() uppercase .PNG | Case-insensitive | `test_ocr_reader.py::test_supports_uppercase` | ✅ COMPLIANT |
| R2 | supports() rechaza .csv/.xlsx | Extensiones no soportadas | `test_ocr_reader.py::test_rejects_other_extensions` | ✅ COMPLIANT |
| R3 | _group_by_rows agrupa por Y-centre | Lista vacía | `test_ocr_reader.py::test_empty` | ✅ COMPLIANT |
| R3 | _group_by_rows agrupa por Y-centre | Una fila, dos celdas | `test_ocr_reader.py::test_single_row` | ✅ COMPLIANT |
| R3 | _group_by_rows agrupa por Y-centre | Dos filas separadas | `test_ocr_reader.py::test_two_rows` | ✅ COMPLIANT |
| R3 | _group_by_rows merge con tolerance alta | Filas cercanas se fusionan | `test_ocr_reader.py::test_tolerance_merges_close_rows` | ✅ COMPLIANT |
| R4 | _detect_header heurística alpha | Fila con alpha es header | `test_ocr_reader.py::test_alpha_row_is_header` | ✅ COMPLIANT |
| R4 | _detect_header heurística alpha | Filas numéricas sin header | `test_ocr_reader.py::test_numeric_rows_no_header` | ✅ COMPLIANT |
| R4 | _detect_header heurística alpha | Header en segunda fila | `test_ocr_reader.py::test_header_on_second_row` | ✅ COMPLIANT |
| R4 | _detect_header salta filas vacías | Empty row skipped | `test_ocr_reader.py::test_empty_row_skipped` | ✅ COMPLIANT |
| R5 | _build_dataframe con header | Columnas nombradas | `test_ocr_reader.py::test_with_header` | ✅ COMPLIANT |
| R5 | _build_dataframe sin header | Columnas genéricas | `test_ocr_reader.py::test_without_header` | ✅ COMPLIANT |
| R5 | _build_dataframe filas desiguales | Padding con None | `test_ocr_reader.py::test_uneven_rows` | ✅ COMPLIANT |
| R6 | detect_reader selecciona OcrReader para .png | Imagen PNG | `test_readers.py::test_detect_reader_returns_ocr_for_png` | ✅ COMPLIANT |
| R6 | detect_reader selecciona OcrReader para .jpg | Imagen JPG | `test_readers.py::test_detect_reader_returns_ocr_for_jpg` | ✅ COMPLIANT |
| R6 | detect_reader selecciona OcrReader para .jpeg | Imagen JPEG | `test_readers.py::test_detect_reader_returns_ocr_for_jpeg` | ✅ COMPLIANT |
| R6 | detect_reader registra OcrReader sin easyocr | Graceful degradation | `test_readers.py::test_detect_reader_registers_ocr_even_without_easyocr` | ✅ COMPLIANT |
| R7 | --ocr flag presente en CLI help | Flags en --help | `test_cli.py::test_compare_help_shows_ocr_flags` | ✅ COMPLIANT |
| R8 | --ocr sin easyocr → error graceful | CLI sin dependencia | `test_cli.py::test_compare_with_ocr_flag_errors_when_easyocr_missing` | ✅ COMPLIANT |

**Compliance summary**: 23/23 escenarios compliant (100%)

*Nota: 7 tests de integración (TestOcrReaderWithEasyOCR) están SKIPPED porque EasyOCR no está instalado. No se reportan como FAIL porque el skip es intencional y esperado — validan el pipeline completo con OCR real.*

### Correctness (Static Evidence)

| Requisito | Estado | Notas |
|-----------|--------|-------|
| OcrReader implementación | ✅ Implementado | 329 líneas, heurística completa, lazy singleton |
| _group_by_rows con tolerancia configurable | ✅ Implementado | np.median para estimación robusta de altura |
| _detect_header con threshold 40% alpha | ✅ Implementado | Alpha threshold = 0.4, salta filas vacías |
| _build_dataframe con padding | ✅ Implementado | None-padding para filas desiguales |
| detect_reader extiende para imágenes | ✅ Implementado | Lazy registration + error informativo para imágenes |
| --ocr + flags asociados en CLI | ✅ Implementado | --ocr, --ocr-language, --ocr-conf-threshold |
| Graceful degradation sin easyocr | ✅ Implementado | OcrReader registrable sin easyocr; ImportError en read(); SystemExit 1 en CLI |
| Fixture sintético | ✅ Implementado | gen_capture_fixture.py + sample-capture.png (5 filas, 4 columnas) |
| Dependencia opcional [ocr] | ✅ Implementado | pyproject.toml con easyocr como optional dep |
| Tests sin easyocr pasan | ✅ Verificado | 87 passed, 7 skipped (0 failures) |

### Coherence (Design)

*No se encontró `design.md`. Las decisiones de diseño se infieren del código y la propuesta:*

| Decisión de Diseño | ¿Seguida? | Notas |
|--------------------|-----------|-------|
| EasyOCR lazy singleton | ✅ Sí | `_get_easyocr()` con `_OCR_INSTANCE` global |
| Agrupación por Y-centre con np.median | ✅ Sí | `_group_by_rows()` con `row_height_tolerance` |
| Header detection por ratio alpha | ✅ Sí | `_detect_header()` con threshold 40% |
| Lazy registration con try/except ImportError | ✅ Sí | `_ensure_readers()` catch ImportError |
| --ocr bypass detect_reader | ✅ Sí | CLI crea OcrReader directamente |
| conf_threshold como filtro post-OCR | ✅ Sí | Filtrado después de readtext() |
| Configuración por constructor + kwargs en read() | ✅ Sí | Parámetros duplicados con override por kwargs |

### Issues Found

**CRITICAL**: None

**WARNING**:
1. **Artefactos faltantes**: `spec.md` y `design.md` no existen en el directorio openspec ni en Engram. Solo se encontraron `proposal.md` y `tasks.md`. La verificación se realizó contra los requisitos extraídos de estos artefactos + inspección de código, pero sin la especificación formal y el diseño no se puede garantizar que el cubrimiento sea completo contra la intención original.
2. **7 tests skipped por falta de EasyOCR**: `TestOcrReaderWithEasyOCR` (integración con el fixture sintético) no se ejecutaron porque EasyOCR no está instalado. La funcionalidad de OCR real no está verificada en este entorno. Esto es esperado y documentado, pero significa que el pipeline OCR completo solo está validado a nivel unitario.

**SUGGESTION**:
1. **Ejecutar con EasyOCR**: Instalar `pip install matchaudit[ocr]` y ejecutar los tests de integración para verificar el pipeline OCR real.
2. **Persistir spec.md y design.md**: Completar el ciclo SDD persistiendo estos artefactos para trazabilidad completa.

### Verdict

**PASS**

El cambio `implementar-lector-de-capturas-ocr` está completo: 15/15 tasks implementados, 23/23 escenarios compliant (100%), 87 tests pasan (7 skipped esperados), lint limpio, CLI flags funcionando. No hay issues críticos. Los WARNINGS son de documentación y entorno (falta EasyOCR para tests de integración).
