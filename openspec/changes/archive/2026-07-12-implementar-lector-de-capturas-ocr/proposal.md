# Proposal: Implementar lector de capturas OCR

## Intent

MatchAudit soporta archivos estructurados (Excel/CSV) pero no imágenes. Los auditores necesitan validar capturas de pantalla de sistemas legacy contra datos fuente. Este cambio agrega un lector OCR que transforma imágenes en DataFrames para integrarse al pipeline de comparación existente.

## Scope

### In Scope
- `OcrReader` implementando `DataReader` via EasyOCR + Pillow
- Algoritmo de reconstrucción de tabla desde bounding boxes (agrupación Y, orden X, detección de header)
- Flag `--ocr` en comando `compare` para forzar OCR
- Auto-detección de imágenes (.png, .jpg, .jpeg) en `detect_reader`
- EasyOCR como dependencia opcional `[ocr]`
- Tests con fixture sintético de captura

### Out of Scope
- OpenCV preprocessing (postergado hasta validación con capturas reales)
- Comando OCR separado (se prioriza pipeline integrado)
- Soporte PDF, TIFF, BMP (solo PNG/JPEG en esta iteración)
- OCR multilenguaje (solo `['en']`)

## Capabilities

### New Capabilities
- `ocr-reading`: lectura de imágenes con EasyOCR y reconstrucción de tablas a DataFrame

### Modified Capabilities
- `data-reading`: extensión del DataReader ABC y `detect_reader` para soportar imágenes; flag `--ocr` en CLI

## Approach

Pipeline integrado: `detect_reader` reconoce .png/.jpg/.jpeg y selecciona `OcrReader`. Este usa EasyOCR para extraer texto con bounding boxes, agrupa detecciones por Y (filas) y ordena por X (columnas), detecta header por heurística de contenido, y construye un DataFrame. El flag `--ocr` fuerza el uso de `OcrReader` para cualquier archivo. El modelo EasyOCR se carga lazy (primer `read()`). EasyOCR como dependencia opcional (`pip install matchaudit[ocr]`).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/matchaudit/readers/__init__.py` | Modified | Extender `detect_reader` y `_ensure_readers` para imágenes |
| `src/matchaudit/readers/ocr.py` | New | OcrReader — implementación DataReader con EasyOCR |
| `src/matchaudit/cli.py` | Modified | Flag `--ocr`, `--ocr-language`, `--ocr-conf-threshold` |
| `pyproject.toml` | Modified | `[project.optional-dependencies] ocr = ["easyocr"]` |
| `tests/test_ocr_reader.py` | New | Tests de reconstrucción y edge cases |
| `tests/fixtures/sample-capture.png` | New | Fixture sintético de captura |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| EasyOCR + PyTorch ~800MB-2GB | High | Dependencia opcional `[ocr]`; documentar |
| Model loading 5-15s en CPU | Med | Lazy loading + singleton; advertir al usuario |
| Precisión en capturas reales <80% | Med | `conf_threshold` configurable; `allowlist` restrictivo |
| Reconstrucción de tabla incorrecta | Med | Tolerancias configurables; tests con múltiples layouts |

## Rollback Plan

1. Revertir `pyproject.toml` — eliminar `[project.optional-dependencies] ocr`
2. Revertir `src/matchaudit/readers/__init__.py` — quitar registros de OcrReader
3. Eliminar `src/matchaudit/readers/ocr.py`
4. Revertir `src/matchaudit/cli.py` — quitar flags `--ocr`
5. Eliminar tests y fixtures de OCR

## Dependencies

- `easyocr` + `pillow` (vía `pip install matchaudit[ocr]`)
- `numpy` (transición PIL → EasyOCR)

## Success Criteria

- [ ] `OcrReader.read()` produce DataFrame correcto desde captura sintética con tabla conocida
- [ ] `detect_reader` selecciona `OcrReader` para .png/.jpg/.jpeg
- [ ] Flag `--ocr` forza OCR sobre archivos .csv/.xlsx
- [ ] `pip install matchaudit` no instala EasyOCR; `pip install matchaudit[ocr]` sí
- [ ] Test suite pasa sin dependencia `[ocr]` instalada
