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

### Paso a paso

```bash
# Clonar el repo
git clone <repo-url>
cd matchaudit

# Sincronizar dependencias base
uv sync

# Verificar que funciona
uv run matchaudit --help

# (Opcional) Instalar soporte OCR para capturas de pantalla
uv sync --extra ocr
```

> **Windows**: EasyOCR y PyTorch CPU funcionan sin problemas. Si tenés GPU NVIDIA, EasyOCR la usa automáticamente (mucho más rápido).

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
