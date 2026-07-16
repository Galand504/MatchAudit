# Exploration: Implementar lector de capturas OCR

## Current State

### Architecture existente
MatchAudit tiene un pipeline consolidado para archivos estructurados:

```
CLI (compare command)
  → detect_reader(path) → reader.read() → DataFrame
  → Comparator.compare(source_df, captured_df, key_columns)
  → render_comparison(result)
```

El `DataReader` ABC en `readers/__init__.py` define `read(path, **kwargs) → DataFrame` y `supports(ext) → bool`. Hoy hay dos implementaciones: `CsvReader` y `ExcelReader`. El factory `detect_reader()` selecciona por extensión de archivo (`.csv`, `.xlsx`, `.xls`).

### Lo que falta
La herramienta fue concebida para validar **capturas de pantalla** contra datos fuente, pero no existe ningún reader que acepte imágenes. El flujo completo está diseñado alrededor de `DataFrame`, así que el OCR reader debe integrarse como un `DataReader` más que produce un `DataFrame` desde una imagen.

### Dependencias actuales
- `click` ≥ 8.1 — CLI
- `pandas` ≥ 2.1 — DataFrames (el contrato de salida)
- `openpyxl` ≥ 3.1 — Excel engine
- `sqlalchemy` ≥ 2.0 — reservado para futuro SQL
- `rich` ≥ 13.7 — output formateado
- **No hay EasyOCR, PyTorch, ni OpenCV** en las dependencias actuales

### Estado de SDD
El proyecto usa estructura OpenSpec con cambios archivados. `openspec/config.yaml` existe con reglas de proyecto. Este es el primer cambio nuevo post-archivo.

---

## EasyOCR Capability Analysis

### API core: `readtext()`
- Input: file path, URL, numpy array (OpenCV), o raw bytes
- Output: `list[(bbox[[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, confidence)]`
  - `bbox` es un cuadrilátero con coordenadas de píxeles (top-left, top-right, bottom-right, bottom-left)
  - `text` es el string reconocido
  - `confidence` es float 0..1
- `detail=0` → solo textos planos
- `paragraph=True` → mergea detecciones cercanas en párrafos
- `output_format='dict' | 'json'` → formatos alternativos
- `allowlist` / `blocklist` → restricción de caracteres (crítico para tablas numéricas)

### Inicialización del Reader
```python
reader = easyocr.Reader(['en'], gpu=False)
```
- Descarga automática de modelos (~100-200MB) al primer uso en `~/.EasyOCR/model/`
- GPU: auto-detecta CUDA o MPS, se desactiva con `gpu=False`
- `quantize=True` — cuantización dinámica en CPU (útil para deploys sin GPU)
- `model_storage_directory` — ruta custom para modelos

### Relevancia para capturas de pantalla
Las capturas de pantalla tienen características ideales para OCR:
- **Texto perfectamente horizontal** — sin skew, sin rotación
- **Fondo blanco/liso** — alto contraste, sin ruido de textura
- **Fuente uniforme** — sin variaciones caligráficas
- **Resolución conocida** — 72-96 DPI típico en pantallas

Esto hace que EasyOCR funcione significativamente mejor que con fotos de documentos.

---

## Table Reconstruction Algorithm from Bounding Boxes

El problema central: EasyOCR devuelve texto plano con coordenadas, no estructura de tabla.

### Paso 1: Agrupar por filas (Y-axis clustering)
Cada bbox tiene un centro Y: `y_center = (y1 + y3) / 2`

```
Para cada detection (bbox, text, conf):
    y_center = (bbox[0][1] + bbox[2][1]) / 2
    asignar a row_group basado en proximidad de y_center
```

**Algoritmo de clustering**: ordenar detections por `y_center`, luego agrupar con tolerancia configurable (e.g. `row_tolerance = alto_fila * 0.6`). El alto de fila se puede estimar como el Y-range típico de los bboxes.

### Paso 2: Ordenar por columnas dentro de cada fila (X-axis ordering)
Dentro de cada grupo de fila, ordenar por `x_center` ascendente:

```
Para cada row_group:
    ordenar detections por x_center
    asignar posición de columna secuencial
```

### Paso 3: Detectar header
Heurística: la primera fila con contenido textual (no numérico) en todas sus celdas es el header. Alternativa: si se pasa `header_rows=N`, usar las primeras N filas como header.

### Paso 4: Reconstruir DataFrame
```
filas = []  # list[dict[column_name, value]]
Para cada row_group después del header:
    row_dict = {}
    Para cada columna en el row_group:
        row_dict[header_value] = text
    filas.append(row_dict)

df = pd.DataFrame(filas)
```

### Edge cases detectados
- **Merged cells**: dos celdas adyacentes con el mismo texto — deduplicar por X-proximidad
- **Celdas vacías (null values)**: regiones sin bbox dentro del rectángulo esperado de la celda
- **Decimales con punto**: EasyOCR reconoce puntos como caracteres, pero pueden confundirse con ruido
- **Números con separadores de miles**: `1,234` vs `1.234` según locale
- **Columnas sin header visible**: si la primera fila parece datos, usar nombres genéricos (col_0, col_1, ...)

---

## Approaches

### 1. **OcrReader standalone (DataReader implementation)**
   Crear `readers/ocr.py` implementando `DataReader`. Lee imagen → EasyOCR → reconstruye DataFrame.
   - **Pros**: Sin cambios en la interfaz existente; `detect_reader` puede soportar `.png`, `.jpg`, `.jpeg`
   - **Cons**: EasyOCR es ~10-100x más lento que leer Excel; modelo descarga 100-200MB; la extensión no diferencia entre foto y captura de tabla
   - **Effort**: Medium

### 2. **OcrReader + preprocesamiento OpenCV**
   Igual que #1 pero agrega pipeline de preprocesamiento: convertir a escala de grises, threshold adaptativo, deskew por si la imagen está rotada, remoción de bordes.
   - **Pros**: Mejora precisión en capturas borderline (fondos grises, texto low-res, compresión JPEG agresiva)
   - **Cons**: OpenCV como dependencia adicional (~30-50MB); complejidad extra para casos que no lo necesitan
   - **Effort**: Medium-High

### 3. **Comando OCR separado en CLI**
   En lugar de integrar en `detect_reader`, crear subcomando `matchaudit ocr <image> --output <csv>` que transforme imagen a CSV primero, y luego el usuario use `compare` con ese CSV.
   - **Pros**: Separación clara de responsabilidades; no contamina el pipeline rápido con latencia OCR; el usuario puede inspeccionar/aditar el CSV intermedio
   - **Cons**: Workflow de dos pasos para el usuario; pierde la integración seamless del pipeline único
   - **Effort**: Low-Medium

### 4. **Pipeline integrado: OCR como reader + --ocr flag**
   Mantener `detect_reader` limpio y agregar flag `--ocr` al comando `compare` que force el uso del OCR reader independientemente de la extensión. El OCR reader se instancia directamente (no por detect_reader). Opcional: auto-detectar si el archivo es imagen por extensión.
   - **Pros**: Lo mejor de ambos mundos; pipeline unificado con flag explícito; no rompe el factory existente
   - **Cons**: Dos caminos de invocación (auto-detect vs flag) puede confundir
   - **Effort**: Medium

---

## Recommendation

**Approach 4: Pipeline integrado con flag `--ocr`** combinado con auto-detección por extensión de imagen en `detect_reader`.

Fundamentos:
1. `detect_reader` se extiende para soportar `.png`, `.jpg`, `.jpeg` → auto-detect sin flag
2. Se agrega flag `--ocr` al comando `compare` para forzar OCR incluso en archivos `.csv`/`.xlsx` (útil cuando el archivo estructurado es en realidad una imagen mal nombrada)
3. El `OcrReader` implementa `DataReader`, usa **EasyOCR** como engine principal + **Pillow** para preprocesamiento ligero (redimensionar, convertir a RGB). Sin OpenCV.
4. El modelo EasyOCR se carga **lazy** (first call a `read()`) para no impactar el tiempo de arranque del CLI
5. `allowlist` se usa para restringir caracteres según el tipo de dato detectado (números, letras, puntuación básica)

### Por qué no OpenCV
- Pillow (que ya viene con pandas/PIL) puede hacer resize y conversión de color
- Las capturas de pantalla no necesitan corrección de perspectiva, deskew complejo, ni threshold adaptativo
- EasyOCR hace su propio preprocesamiento interno (CRAFT detector maneja ruido leve)

### Algoritmo de reconstrucción
```
read(path):
  img = Image.open(path).convert("RGB")
  img_array = numpy.array(img)
  
  results = reader.readtext(img_array, detail=1)
  
  # Agrupar por Y
  groups = group_by_row(results, y_tolerance=row_height * 0.6)
  
  # Detectar header (primera fila con >50% texto alpha)
  header_line = detect_header(groups)
  
  # Construir DataFrame
  df = build_dataframe(groups, header_line)
  
  return df
```

**Parámetros configurables** (via kwargs):
- `row_tolerance`: tolerancia de agrupación Y (default derivado de altura de imagen / número de filas estimado)
- `header_rows`: número de filas de header (default auto-detect)
- `conf_threshold`: mínimo confidence para incluir detección (default 0.3)
- `language`: lenguajes para EasyOCR (default `['en']`)
- `allowlist`: caracteres permitidos (default ninguno — EasyOCR usa su set completo)

---

## Affected Areas

| File | Action | Why |
|------|--------|-----|
| `src/matchaudit/readers/__init__.py` | **Modify** | Agregar soporte de extensiones `.png`, `.jpg`, `.jpeg` en `detect_reader`; registrar `OcrReader` en `_ensure_readers` |
| `src/matchaudit/readers/ocr.py` | **Create** | `OcrReader` — implementación de `DataReader` con EasyOCR + algoritmo de reconstrucción de tabla |
| `src/matchaudit/cli.py` | **Modify** | Agregar flag `--ocr` (y opcionalmente `--ocr-language`, `--ocr-conf-threshold`) al comando `compare` |
| `pyproject.toml` | **Modify** | Agregar `easyocr` como dependencia opcional (`[project.optional-dependencies] ocr = ["easyocr"]`) y `pillow` (si no está ya como dependencia de pandas/openpyxl) |
| `tests/test_readers.py` | **Modify** | Agregar tests para `OcrReader` — `supports()` con extensiones de imagen, test de fixture de captura |
| `tests/fixtures/` | **Add** | Agregar imagen de test (`sample-capture.png`) con tabla conocida para tests de reconstrucción OCR |
| `tests/test_ocr_reader.py` | **Create** | Tests específicos del OCR: algoritmo de agrupación, detección de header, caracteres mal reconocidos, edge cases |
| `openspec/changes/implementar-lector-de-capturas-ocr/state.yaml` | **Create** | SDD state tracking |

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Precisión de EasyOCR en capturas reales** — aunque las capturas de pantalla son ideales, fondos grises, texto pequeño (<10px), o compresión JPEG agresiva pueden degradar la precisión | **Medium** | Pruebas con fixtures reales de captura; umbral de confidence configurable; permitlist para restringir caracteres; si la precisión es <80%, documentar como limitación conocida |
| **Rendimiento — model loading** — EasyOCR carga modelo PyTorch de ~100-200MB al primer `read()`, que puede tomar 5-15 segundos en CPU | **Medium** | Lazy loading del Reader (no al importar el módulo); singleton para reusar la instancia entre llamadas; `gpu=False` con `quantize=True` para acelerar CPU; advertencia al usuario en primera ejecución |
| **Rendimiento — procesamiento por imagen** — EasyOCR toma 1-5 segundos por imagen en CPU (dependiendo de resolución) | **Medium** | Escalar imágenes grandes a ~1280px de ancho antes de pasar a EasyOCR; documentar que OCR es ~10-100x más lento que leer Excel |
| **Estructura de tabla inconsistente** — columnas sin alinear visualmente, headers con varias líneas, tablas sin bordes pueden producir reconstrucción incorrecta | **High** | El algoritmo de agrupación debe tener tolerancias configurables; pruebas con distintos layouts; fallback a CSV intermedio para que el usuario pueda corregir |
| **Caracteres mal reconocidos** — `0` vs `O`, `1` vs `l`/`I`, `5` vs `S`, espacios vs sin espacios | **Medium** | `allowlist` restrictivo para columnas numéricas (solo dígitos, punto, guión); campo de confianza para reportar detecciones dudosas al usuario |
| **Dependencia EasyOCR + PyTorch** — EasyOCR instala PyTorch como dependencia, que es ~800MB en Linux (CPU) o ~2GB (CUDA). Es una dependencia heavy para una CLI | **High** | EasyOCR como dependencia **opcional** (`pip install matchaudit[ocr]`); documentar claramente el peso; si no se necesita OCR, `pip install matchaudit` queda liviano |
| **Orden de columnas inestable** — dos celdas con mismo X-center pueden intercambiar orden si el clustering es impreciso | **Medium** | Usar X-center + tolerancia; si dos celdas tienen X-center dentro de tolerancia, usar la posición de columna esperada según el header |
| **Múltiples imágenes en una captura** — la imagen puede contener tablas + otros elementos | **Low** | EasyOCR solo devuelve texto detectado; el algoritmo agrupa todo lo que encuentra; documentar que el reader espera una sola tabla en la imagen |

---

## Ready for Proposal

**Yes.** La exploración confirma:

1. **EasyOCR** es la herramienta correcta para el pipeline OCR: soporta capturas de pantalla (texto horizontal, fondo blanco), API clara con bounding boxes, confidence scores, y allowlist
2. **El algoritmo de reconstrucción de tabla** desde bounding boxes es viable: agrupar por Y (filas), ordenar por X (columnas), detectar header por heurística de tipo de contenido
3. **La integración como `DataReader`** respeta la arquitectura existente — `OcrReader` implementa la misma interfaz que `CsvReader`/`ExcelReader`. La extensión de `detect_reader` para soportar `.png/.jpg/.jpeg` es natural
4. **El flag `--ocr`** da flexibilidad sin romper el pipeline existente
5. **EasyOCR como dependencia opcional** es crítica para mantener `pip install matchaudit` liviano

### Lo que debe considerar el orchestrator antes de `sdd-propose`:
- **Confirmar**: ¿EasyOCR como dependencia opcional `[ocr]` es aceptable, o se quiere incluir por defecto? Si se incluye por defecto, `pip install matchaudit` pasará de ~50MB a ~900MB+ (con PyTorch CPU).
- **Priorizar**: ¿Se implementa primero el `OcrReader` con `detect_reader` extendido, o primero el flag `--ocr` en CLI? El orden recomendado es: (1) EasyOCR + Pillow en dependencias opcionales, (2) `OcrReader` + algoritmo de reconstrucción, (3) tests con fixture de captura real, (4) flag `--ocr` y extensión de `detect_reader`, (5) tests de integración CLI.
- **Postergar**: La pregunta sobre OpenCV puede resolverse en el diseño si las pruebas con capturas reales muestran necesidad de preprocesamiento adicional.
