# MatchAudit

Herramienta de **validación y reconciliación** para equipos de auditoría: verifica que los datos mostrados en capturas de pantalla de sistemas (phpMyAdmin, paneles, reportes) coincidan exactamente con los datos fuente exportados (Excel, CSV).

## ¿Para qué sirve?

Un auditor necesita confirmar que lo que **se ve en pantalla** es exactamente lo que **está en la base de datos**. MatchAudit automatiza esta verificación:

1. Toma el **archivo fuente** (exportación Excel/CSV de la BD)
2. Toma la **captura de pantalla** del sistema (phpMyAdmin, etc.)
3. Aplica OCR para extraer los datos de la imagen
4. Compara fila por fila y reporta **cada diferencia**

## Stack

- **Python** 3.11+
- **CLI**: Click
- **Datos**: Pandas, openpyxl
- **OCR**: EasyOCR + PyTorch (CPU)
- **Output**: Rich (terminal con colores)
- **Build**: uv

## Instalación

### Prerrequisitos

- Python 3.11 o superior
- [uv](https://docs.astral.sh/uv/) — instalalo con:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Instalación base (Excel/CSV — recomendado siempre)

```bash
git clone <repo-url>
cd matchaudit
uv sync
uv run matchaudit --help
```

Con esto ya funciona para comparar **archivos Excel vs Excel, CSV vs CSV, o Excel vs CSV**.

### EasyOCR (solo para capturas de pantalla)

Si vas a comparar contra **imágenes** (.png, .jpg), necesitás EasyOCR:

```bash
uv sync --extra ocr
```

> **Windows**: EasyOCR + PyTorch CPU funcionan sin problemas. Si tenés GPU NVIDIA, EasyOCR la detecta automáticamente (mucho más rápido).

> **Linux**: Si ves errores de torch durante la instalación, probá `uv sync --extra ocr --no-build-isolation`.

### GUI (interfaz gráfica)

Si preferís una ventana en vez de terminal:

```bash
uv sync --extra gui
uv run matchaudit-gui
```

Para tener OCR + GUI:

```bash
uv sync --extra ocr --extra gui
# o directamente:
uv sync --extra full
```

## Uso

### Lo más simple — todo automático

```bash
uv run matchaudit compare \
  --source datos_exportados.xlsx \
  --captured captura_pantalla.png
```

MatchAudit **auto-detecta**:
- OCR cuando el archivo es `.png`, `.jpg` o `.jpeg`
- Idioma español + inglés (`es,en`) para OCR por defecto
- La columna clave para cruzar los datos (`id`, `nombre`, `codigo`, etc.)

### Con todas las opciones

```bash
uv run matchaudit compare \
  --source datos_exportados.xlsx \
  --captured captura_pantalla.png \
  --key-columns id_pais \
  --label-column nombre \
  --start Suiza \
  --end Zimbabue \
  --ocr-upscale \
  --ocr-language es,en
```

### Opciones disponibles

| Opción | Por defecto | Descripción |
|--------|-------------|-------------|
| `--source` | **(requerido)** | Archivo fuente (Excel, CSV o imagen) |
| `--captured` | **(requerido)** | Archivo capturado (imagen, Excel o CSV) |
| `--key-columns` | auto-detectada | Columna(s) para identificar filas únicas |
| `--label-column` | — | Columna para acotar por rango (ej: `nombre`) |
| `--start` / `--end` | — | Valores de inicio/fin del rango |
| `--output` | consola | Formato de salida: `json` |
| `--ocr-language` | `es,en` | Idiomas para OCR (separados por coma) |
| `--ocr-conf-threshold` | `0.0` | Umbral de confianza OCR (0.0–1.0) |
| `--ocr-upscale` | `no` | Escalar imagen antes de OCR (más lento, detecta IDs chicos) |

### Interfaz gráfica

También tenés `matchaudit-gui` que abre una ventana sin necesidad de terminal:

```bash
uv run matchaudit-gui
```

### Modos de velocidad

| Modo | Comando | Tiempo aprox | Precisión |
|------|---------|-------------|-----------|
| **Rápido** (sin upscale) | `--ocr` | ~1 min | No detecta IDs muy pequeños |
| **Preciso** (con upscale) | `--ocr --ocr-upscale` | ~3-5 min | Detecta IDs desde 8+ |
| **Sin OCR** (Excel vs Excel) | (ningún flag) | <1 seg | 100% |

## Ejemplos con datos reales

### País por país — comparar Excel contra captura de phpMyAdmin

```bash
# Último registro (Suiza → Zimbabue, IDs grandes → 100% match)
uv run matchaudit compare \
  --source gestion_investigacion_paises.xlsx \
  --captured Ultimo_registro.png \
  --key-columns id_pais \
  --label-column nombre \
  --start Suiza \
  --end Zimbabue \
  --ocr-upscale
```

```
┌────────────────────────────────── MISMATCH ──────────────────────────────────┐
│ Match rate: 100.0%                                                           │
│ Matched rows:         25                                                     │
│ Mismatched cells:     0                                                      │
│ Missing rows:         0                                                      │
│ Extra rows:           0                                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

```bash
# Primer registro (Afganistán → Botsuana, IDs 1-7 no detectables sin upscale)
uv run matchaudit compare \
  --source gestion_investigacion_paises.xlsx \
  --captured primer_registro.png \
  --key-columns nombre \
  --label-column nombre \
  --start Afganistán \
  --end Botsuana
```

```
┌──────────────────────────── MISMATCH (CRITICAL) ─────────────────────────────┐
│ Match rate: 92.0%                                                            │
│ Matched rows:         23                                                     │
│ Mismatched cells:     53                                                     │
│ Missing rows:         2                                                      │
│ Extra rows:           2                                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Comparación por lotes

Si tenés una carpeta con fuentes y otra con capturas, `batch-compare` las empareja
por nombre de archivo y las procesa todas juntas:

```bash
uv run matchaudit batch-compare \
  --source-dir ./reportes \
  --captured-dir ./capturas
```

Con `--prefix-match`, un mismo source se compara contra múltiples capturas que
compartan el prefijo del nombre:

```bash
# usuarios.csv se compara contra usuarios_primer.png y usuarios_ultimo.png
uv run matchaudit batch-compare \
  --source-dir ./reportes \
  --captured-dir ./capturas \
  --prefix-match
```

### Tipos de diferencias que MatchAudit detecta

| Tipo | Ejemplo | Causa |
|------|---------|-------|
| **OCR impreciso** | `Zimbabue` → `Zinbabue` | EasyOCR se equivoca |
| **Conector "y"** | `Antigua y Barbuda` → `Antigua Barbuda` | OCR omite palabras cortas |
| **Espacio en fecha** | `2026-05-31 19:57:08` → `2026-05-3119:57:08` | Texto muy compacto (se auto-corrige) |
| **IDs no detectados** | `id_pais=1` → vacío | Números muy pequeños en fondo oscuro |
| **Columna faltante** | 25 filas en captura vs 193 en Excel | La captura solo muestra una página |
| **Dato modificado** | `updated_at` diferente | El registro cambió entre la captura y la exportación |

## Output

Por defecto MatchAudit muestra una tabla con colores en la terminal:
- **Verde** → filas que coinciden
- **Rojo** → filas faltantes o extra
- **Amarillo** → diferencias en celdas específicas

Para salida JSON (ideal para integrar con otras herramientas):

```bash
uv run matchaudit compare ... --output json
```

## Portable (ejecutable sin Python)

Podés generar un `.exe` (o ejecutable Linux/macOS) que no necesita Python instalado:

```bash
# Windows — doble click o:
scripts\build.bat

# Linux / macOS:
./scripts/build.sh
```

El resultado queda en `dist/MatchAudit/` — una carpeta portable que podés
zippear y distribuir. Ejecutás `MatchAudit.exe` y abre la GUI directo.

> **Nota**: EasyOCR + PyTorch pesan ~2 GB, la carpeta final va a ser grande.
> En máquinas con GPU NVIDIA el OCR corre mucho más rápido.

## Desarrollo

```bash
# Tests
uv run pytest

# Linting
uv run ruff check src/

# Formateo
uv run ruff format src/
```

## Licencia

MIT
