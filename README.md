# MatchAudit

Herramienta de **validación y reconciliación** para auditoría: verifica que los datos mostrados en capturas de pantalla coincidan exactamente con los datos fuente exportados (Excel, CSV, SQL).

## Stack

- **Python** 3.11+
- **CLI**: Click
- **Datos**: Pandas, openpyxl, SQLAlchemy
- **Output**: Rich (terminal)
- **Build**: uv

## Quick start

### Prerrequisitos

- Python 3.11 o superior
- [uv](https://docs.astral.sh/uv/) — instalalo con:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Instalación

```bash
# Clonar el repo
git clone <repo-url>
cd matchaudit

# Sincronizar dependencias
uv sync

# Verificar que funciona
uv run matchaudit --help
```

### Desarrollo

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
