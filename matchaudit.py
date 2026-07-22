#!/usr/bin/env python3
"""MatchAudit — data validation and reconciliation tool for audit teams.

Single-file distribution for portable .exe build.
Built from the modular ``src/matchaudit/`` package.

Usage:
    python matchaudit.py compare --source data.csv --captured capture.png
    python matchaudit.py batch-compare --source-dir ./sources --captured-dir ./captures
"""

from __future__ import annotations

import json
import re as _re
import sys
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

# ==============================================================================
# Version
# ==============================================================================

__version__ = "0.1.0"

# ==============================================================================
# Domain models
# ==============================================================================

import pandas as pd  # noqa: E402


@dataclass
class ControlPoint:
    """A named window into a source dataset that must be verified."""

    name: str
    source: pd.DataFrame
    label_column: str
    start_label: Any
    end_label: Any
    description: str = ""


@dataclass
class RowDiff:
    """A single cell-level difference between expected and captured data."""

    index: int
    key: Any
    column: str | None
    expected: Any
    actual: Any


@dataclass
class RowShift:
    """A record present in both datasets but at a different position."""

    expected_position: int
    actual_position: int
    key: Any
    surrounding_rows: tuple[Any, Any]


@dataclass
class ComparisonStats:
    """Aggregated statistics from a comparison run."""

    total_expected: int
    total_captured: int
    match_rate: float
    has_misalignment: bool
    severity: Literal["ok", "warning", "critical"]


@dataclass
class ComparisonResult:
    """The complete output of comparing two datasets."""

    status: Literal["match", "mismatch", "error"]
    matched_rows: int
    mismatched_rows: list[RowDiff] = field(default_factory=list)
    missing_rows: list[RowDiff] = field(default_factory=list)
    extra_rows: list[RowDiff] = field(default_factory=list)
    shifted_rows: list[RowShift] = field(default_factory=list)
    stats: ComparisonStats | None = None


# ==============================================================================
# Control point operations
# ==============================================================================


def extract_control_point(
    df: pd.DataFrame,
    label_column: str,
    start_label: Any,
    end_label: Any,
) -> pd.DataFrame:
    """Extract a slice of *df* between *start_label* and *end_label* (inclusive)."""
    if label_column not in df.columns:
        raise ValueError(
            f"Column {label_column!r} not found in DataFrame. "
            f"Available columns: {list(df.columns)}"
        )
    sorted_df = df.sort_values(by=label_column).reset_index(drop=True)
    mask = (sorted_df[label_column] >= start_label) & (
        sorted_df[label_column] <= end_label
    )
    return sorted_df[mask].reset_index(drop=True)


def validate_unique_keys(
    df: pd.DataFrame,
    key_columns: list[str],
    label: str = "DataFrame",
) -> None:
    """Check that the combination of *key_columns* is unique in *df*."""
    if not key_columns:
        return
    missing = [col for col in key_columns if col not in df.columns]
    if missing:
        raise ValueError(
            f"Key columns {missing} not found in {label}. "
            f"Available columns: {list(df.columns)}"
        )
    duplicates = df[df.duplicated(subset=key_columns, keep=False)]
    if not duplicates.empty:
        raise ValueError(
            f"Duplicate key combinations found in {label}. "
            f"Key columns: {key_columns}. "
            f"Number of duplicate rows: {len(duplicates)}."
        )


# ==============================================================================
# Output formatters
# ==============================================================================


def _safe_str(val: Any) -> str | None:
    """Return a string representation or ``None`` for null-like values."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return str(val)
    return str(val)


def _stats_to_dict(stats: ComparisonStats) -> dict[str, Any]:
    return {
        "total_expected": stats.total_expected,
        "total_captured": stats.total_captured,
        "match_rate": stats.match_rate,
        "has_misalignment": stats.has_misalignment,
        "severity": stats.severity,
    }


def _diff_to_dict(d: RowDiff) -> dict[str, Any]:
    return {
        "index": d.index,
        "key": _safe_str(d.key),
        "column": d.column,
        "expected": _safe_str(d.expected),
        "actual": _safe_str(d.actual),
    }


def _shift_to_dict(s: RowShift) -> dict[str, Any]:
    return {
        "expected_position": s.expected_position,
        "actual_position": s.actual_position,
        "key": _safe_str(s.key),
        "surrounding_rows": [
            _safe_str(s.surrounding_rows[0]),
            _safe_str(s.surrounding_rows[1]),
        ],
    }


def _result_to_dict(result: ComparisonResult) -> dict[str, Any]:
    """Convert a ``ComparisonResult`` to a plain JSON-safe dict."""
    return {
        "status": result.status,
        "matched_rows": result.matched_rows,
        "stats": _stats_to_dict(result.stats) if result.stats else None,
        "mismatched_rows": [_diff_to_dict(d) for d in result.mismatched_rows],
        "missing_rows": [_diff_to_dict(d) for d in result.missing_rows],
        "extra_rows": [_diff_to_dict(d) for d in result.extra_rows],
        "shifted_rows": [_shift_to_dict(s) for s in result.shifted_rows],
    }


def _render_json(result: ComparisonResult) -> None:
    """Write the comparison result as a JSON object to stdout."""
    data = _result_to_dict(result)
    json.dump(data, sys.stdout, indent=2, default=str, ensure_ascii=False)
    sys.stdout.write("\n")


def _render_rich(result: ComparisonResult) -> None:
    """Render via Rich, respecting TTY detection."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    # Summary panel
    stats = result.stats
    if stats is not None:
        if stats.severity == "ok":
            title = "[bold green]MATCH[/bold green]"
            border_style = "green"
        elif stats.severity == "critical":
            title = "[bold red]MISMATCH (CRITICAL)[/bold red]"
            border_style = "red"
        else:
            title = "[bold yellow]MISMATCH[/bold yellow]"
            border_style = "yellow"

        lines = [
            f"Match rate: [bold]{stats.match_rate:.1%}[/bold]",
            "",
            f"Total expected rows:  {stats.total_expected}",
            f"Total captured rows:  {stats.total_captured}",
            f"Matched rows:         {result.matched_rows}",
            f"Mismatched cells:     {len(result.mismatched_rows)}",
            f"Missing rows:         {len(result.missing_rows)}",
            f"Extra rows:           {len(result.extra_rows)}",
            f"Shifted rows:         {len(result.shifted_rows)}",
        ]
        console.print(Panel("\n".join(lines), title=title, border_style=border_style))

    # Diff table
    if result.mismatched_rows:
        table = Table(title="Cell-Level Differences")
        table.add_column("Index", style="dim")
        table.add_column("Key")
        table.add_column("Column")
        table.add_column("Expected", style="cyan")
        table.add_column("Actual", style="red")
        for d in result.mismatched_rows:
            table.add_row(
                str(d.index),
                _safe_str(d.key) or "",
                d.column or "\u2014",
                _safe_str(d.expected) or "(empty)",
                _safe_str(d.actual) or "(empty)",
            )
        console.print(table)

    # Missing rows
    if result.missing_rows:
        table = Table(title="Missing Rows (in source, not in captured)")
        table.add_column("Index", style="dim")
        table.add_column("Key")
        for d in result.missing_rows:
            table.add_row(str(d.index), _safe_str(d.key) or "")
        console.print(table)

    # Extra rows
    if result.extra_rows:
        table = Table(title="Extra Rows (in captured, not in source)")
        table.add_column("Index", style="dim")
        table.add_column("Key")
        for d in result.extra_rows:
            table.add_row(str(d.index), _safe_str(d.key) or "")
        console.print(table)


def render_comparison(
    result: ComparisonResult,
    output_format: str | None = None,
) -> None:
    """Render a ``ComparisonResult`` to stdout."""
    if output_format == "json":
        _render_json(result)
        return
    _render_rich(result)


# ==============================================================================
# Data readers
# ==============================================================================


class DataReader(ABC):
    """Abstract interface for all data source readers."""

    @abstractmethod
    def read(self, path: Path, **kwargs: object) -> pd.DataFrame:
        """Read a data source and return its contents as a DataFrame."""
        ...

    @abstractmethod
    def supports(self, ext: str) -> bool:
        """Return ``True`` if this reader can handle the given file extension."""
        ...


class CsvReader(DataReader):
    """Read CSV files using ``pd.read_csv()`` with sensible defaults."""

    def read(self, path: Path, **kwargs: object) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")
        encoding = kwargs.pop("encoding", "utf-8-sig")
        return pd.read_csv(path, encoding=encoding, **kwargs)  # type: ignore[arg-type]

    def supports(self, ext: str) -> bool:
        return ext == ".csv"


class ExcelReader(DataReader):
    """Read Excel (.xlsx) files using ``pd.read_excel(engine='openpyxl')``."""

    def read(self, path: Path, **kwargs: object) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"Excel file not found: {path}")
        return pd.read_excel(path, engine="openpyxl", **kwargs)  # type: ignore[arg-type]

    def supports(self, ext: str) -> bool:
        return ext in {".xlsx", ".xls"}


# ==============================================================================
# OCR reader — EasyOCR integration
# ==============================================================================

# Lazy optional dependencies — each guarded so the module loads gracefully
# when not installed (CI, minimal environments).

_OCR_INSTANCE: object | None = None

try:
    import numpy as np  # noqa: F811, E402
except ImportError:
    np = None  # type: ignore[assignment]

try:
    from PIL import Image  # noqa: F811, E402
except ImportError:
    Image = None  # type: ignore[assignment]

try:
    import easyocr  # noqa: F811, E402
    _HAS_EASYOCR = True
except ImportError:
    _HAS_EASYOCR = False


# Suppress noisy PyTorch/EasyOCR deprecation warnings
warnings.filterwarnings("ignore", message="torch.quantize_per_tensor")
warnings.filterwarnings("ignore", message="torch.ao.quantization is deprecated")
warnings.filterwarnings("ignore", message="pin_memory.*argument is set as true")


def _get_easyocr(languages: list[str] | None = None, gpu: bool = False) -> object:
    """Return the shared EasyOCR ``Reader`` singleton (created on first call)."""
    global _OCR_INSTANCE
    if _OCR_INSTANCE is None:
        if not _HAS_EASYOCR:
            raise ImportError(
                "EasyOCR is not installed. "
                "Install it with: pip install matchaudit[ocr]"
            )
        _OCR_INSTANCE = easyocr.Reader(languages or ["en"], gpu=gpu)
    return _OCR_INSTANCE


# -- Row-grouping helpers -------------------------------------------------

_DATE_TIME_FIX = _re.compile(r"(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}:\d{2})")


def _bbox_y_center(bbox: list[list[float]]) -> float:
    return (bbox[0][1] + bbox[2][1]) / 2.0


def _bbox_height(bbox: list[list[float]]) -> float:
    return abs(bbox[2][1] - bbox[0][1])


def _bbox_x_center(bbox: list[list[float]]) -> float:
    return (bbox[0][0] + bbox[2][0]) / 2.0


def _bbox_x_start(bbox: list[list[float]]) -> float:
    return bbox[0][0]


def _bbox_x_end(bbox: list[list[float]]) -> float:
    return bbox[2][0]


def _postprocess_text(text: str) -> str:
    """Clean up common OCR artifacts in a cell's text."""
    if not text:
        return text
    result = text.strip()
    result = _DATE_TIME_FIX.sub(r"\1 \2", result)
    result = _re.sub(r" {2,}", " ", result)
    result = _re.sub(r"^[^\w\d]+", "", result)
    result = _re.sub(r"[^\w\d]+$", "", result)
    return result


_KNOWN_COLUMN_NAMES = {
    "id", "id_revista", "nombre", "tipo", "issn", "editorial",
    "periodicidad", "sitio_web", "email", "email_contacto",
    "descripcion", "anio_fundacion", "factor_impacto",
    "idioma_principal", "indexacion", "activa", "created_at",
    "updated_at", "id_pais", "pais", "status", "estado",
    "fecha", "date", "amount", "monto", "total", "precio",
    "name", "code", "codigo", "value", "valor", "description",
    "country", "email", "phone", "telefono", "address", "direccion",
    "codigo_iso2", "codigo_iso3", "codigo_telefono",
}

_OCR_HEADER_ALIASES: dict[str, str] = {
    "lid pais": "id_pais",
    "lid": "id",
    "codigo iso2": "codigo_iso2",
    "codigo is02": "codigo_iso2",
    "codigo_is02": "codigo_iso2",
    "codigo is03": "codigo_iso3",
    "codigo_is03": "codigo_iso3",
    "codigo_tele fono": "codigo_telefono",
    "created at": "created_at",
    "updated at": "updated_at",
}


def _estimate_char_width(
    row: list[tuple[list[list[float]], str, float]],
) -> float:
    widths: list[float] = []
    for bbox, text, _ in row:
        w = _bbox_x_end(bbox) - _bbox_x_start(bbox)
        tl = len(text.strip())
        if tl > 1:
            widths.append(w / tl)
    return float(np.median(widths)) if widths else 10.0


def _group_by_rows(
    results: list[tuple[list[list[float]], str, float]],
    row_height_tolerance: float = 0.6,
) -> list[list[tuple[list[list[float]], str, float]]]:
    """Group EasyOCR detections into rows by Y-centre proximity."""
    if not results:
        return []

    items: list[tuple[float, float, float, list[list[float]], str, float]] = []
    for bbox, text, conf in results:
        yc = _bbox_y_center(bbox)
        h = _bbox_height(bbox)
        xc = _bbox_x_center(bbox)
        items.append((yc, h, xc, bbox, text, conf))

    items.sort(key=lambda t: t[0])

    heights = [h for _, h, _, _, _, _ in items]
    median_height = float(np.median(heights)) if heights else 20.0
    y_tolerance = median_height * row_height_tolerance

    groups: list[list[tuple[list[list[float]], str, float]]] = []
    current_group: list[tuple[float, list[list[float]], str, float]] = []
    current_y = items[0][0]

    for yc, _h, xc, bbox, text, conf in items:
        if abs(yc - current_y) > y_tolerance:
            current_group.sort(key=lambda t: t[0])
            groups.append([(b, t, c) for _, b, t, c in current_group])
            current_group = []
            current_y = yc
        current_group.append((xc, bbox, text, conf))

    if current_group:
        current_group.sort(key=lambda t: t[0])
        groups.append([(b, t, c) for _, b, t, c in current_group])

    return groups


def _cluster_row_by_x_gap(
    row: list[tuple[list[list[float]], str, float]],
    gap_factor: float = 4.0,
) -> list[list[tuple[list[list[float]], str, float]]]:
    """Cluster detections within a row into cells by X-gap proximity."""
    if not row:
        return []

    sorted_row = sorted(row, key=lambda x: _bbox_x_center(x[0]))
    char_w = _estimate_char_width(sorted_row)
    gap_threshold = char_w * gap_factor

    clusters: list[list[tuple[list[list[float]], str, float]]] = []
    current: list[tuple[list[list[float]], str, float]] = [sorted_row[0]]

    for i in range(1, len(sorted_row)):
        prev_end = _bbox_x_end(sorted_row[i - 1][0])
        curr_start = _bbox_x_start(sorted_row[i][0])
        gap = curr_start - prev_end

        if gap < gap_threshold:
            current.append(sorted_row[i])
        else:
            clusters.append(current)
            current = [sorted_row[i]]

    if current:
        clusters.append(current)

    return clusters


def _get_column_names_from_header(
    header_cells: list[list[tuple[list[list[float]], str, float]]],
    column_spread: float = 0.5,
) -> list[tuple[str, float, float, float]]:
    """Extract column names and X-boundaries from clustered header cells."""
    expanded: list[list[tuple[list[list[float]], str, float]]] = []
    for cell in header_cells:
        detections_texts = [(t.strip(), bbox) for bbox, t, _ in cell]
        known_matches = sum(
            1 for t, _ in detections_texts
            if any(kw == t.lower() for kw in _KNOWN_COLUMN_NAMES)
        )
        if known_matches >= 2:
            for bbox, t, conf in cell:
                expanded.append([(bbox, t, conf)])
        else:
            expanded.append(cell)

    expanded.sort(key=lambda c: min(_bbox_x_start(b) for b, _, _ in c))

    columns: list[tuple[str, float, float, float]] = []
    n = len(expanded)

    all_x_ends = [
        _bbox_x_end(b) for cell in expanded for b, _, _ in cell
    ]
    est_width = max(all_x_ends) + 50 if all_x_ends else 2000

    for i, cell in enumerate(expanded):
        text = " ".join(t.strip() for _, t, _ in cell).strip()
        if not text:
            continue
        x_start = min(_bbox_x_start(bbox) for bbox, _, _ in cell)
        x_end = max(_bbox_x_end(bbox) for bbox, _, _ in cell)
        x_center = (x_start + x_end) / 2.0

        if i + 1 < n:
            next_start = min(_bbox_x_start(b) for b, _, _ in expanded[i + 1])
            x_end = (x_end + next_start) / 2.0
        else:
            x_end += est_width * 0.12

        if i > 0:
            prev_end = max(_bbox_x_end(b) for b, _, _ in expanded[i - 1])
            x_start = (x_start + prev_end) / 2.0
        else:
            x_start = max(0, x_start - est_width * 0.02)

        columns.append((text.lower(), x_start, x_end, x_center))

    columns = [
        (_OCR_HEADER_ALIASES.get(name, name), xs, xe, xc)
        for name, xs, xe, xc in columns
    ]
    return columns


def _reconstruct_table_v3(
    results: list[tuple[list[list[float]], str, float]],
    row_height_tolerance: float = 0.6,
    gap_factor: float = 3.0,
) -> pd.DataFrame:
    """Reconstruct a table using X-gap column clustering."""
    rows = _group_by_rows(results, row_height_tolerance=row_height_tolerance)
    if not rows:
        return pd.DataFrame()

    header_idx = _detect_header(rows)
    if header_idx is None:
        return _build_dataframe(rows, None)

    header_row = rows[header_idx]
    data_rows = rows[header_idx + 1:]

    if not data_rows:
        return pd.DataFrame()

    header_cells = _cluster_row_by_x_gap(header_row, gap_factor=gap_factor)
    all_columns = _get_column_names_from_header(header_cells)

    if not all_columns:
        return _build_dataframe(data_rows, header_row)

    data_columns = [
        (name, xs, xe, xc) for name, xs, xe, xc in all_columns
        if any(kw == name for kw in _KNOWN_COLUMN_NAMES)
        or any(kw in name.split() for kw in _KNOWN_COLUMN_NAMES)
        or "_" in name
    ]

    if not data_columns:
        data_columns = all_columns

    col_names = [c[0] for c in data_columns]

    def _assign_cells(
        _cells: list[list[tuple[list[list[float]], str, float]]],
    ) -> dict[str, str | None]:
        _rec: dict[str, str | None] = {c: None for c in col_names}
        for _cell in _cells:
            cell_text = " ".join(t.strip() for _, t, _ in _cell).strip()
            if not cell_text:
                continue
            cell_text = _postprocess_text(cell_text)
            if not cell_text:
                continue
            cell_xc = _bbox_x_center(_cell[0][0])
            candidates = [
                c for c in data_columns if c[1] <= cell_xc <= c[2]
            ]
            if not candidates:
                continue
            best_col = min(candidates, key=lambda c: abs(cell_xc - c[3]))
            _rec[best_col[0]] = cell_text
        return _rec

    min_data_cols = max(len(col_names) // 2, 2)
    records: list[dict[str, str | None]] = []

    i = 0
    while i < len(data_rows):
        row = data_rows[i]
        cells = _cluster_row_by_x_gap(row, gap_factor=gap_factor)
        record = _assign_cells(cells)
        vals = [v for v in record.values() if v is not None]

        merged = False
        if len(vals) < min_data_cols and i + 1 < len(data_rows):
            next_cells = _cluster_row_by_x_gap(data_rows[i + 1], gap_factor=gap_factor)
            next_record = _assign_cells(next_cells)
            next_vals = [v for v in next_record.values() if v is not None]
            has_overlap = any(
                record[c] is not None and next_record[c] is not None
                for c in col_names
            )
            combined_vals = vals + next_vals
            if not has_overlap and len(combined_vals) >= min_data_cols:
                merged_rec = {**record}
                for c in col_names:
                    if next_record[c] is not None:
                        merged_rec[c] = next_record[c]
                record = merged_rec
                vals = [v for v in record.values() if v is not None]
                merged = True
                i += 1

        if len(vals) >= min_data_cols:
            has_footer = any(
                v and _re.search(
                    r"(?:^showing|rows per page|page \d+ of|\d+-\d+ of )",
                    v.lower(),
                )
                for v in vals
            )
            if not has_footer:
                if record not in records:
                    records.append(record)
        i += 1

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


_ALPHA_THRESHOLD = 0.4


def _has_alpha(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


def _is_numeric_cell(text: str) -> bool:
    stripped = text.strip().replace(",", "").replace(".", "").replace("-", "")
    return stripped.isdigit() or text == ""


def _row_has_known_columns(
    row: list[tuple[list[list[float]], str, float]],
    min_matches: int = 3,
) -> bool:
    matches = 0
    for _, text, _ in row:
        normalized = text.strip().lower()
        if normalized in _KNOWN_COLUMN_NAMES:
            matches += 1
    return matches >= min_matches


def _detect_header(
    rows: list[list[tuple[list[list[float]], str, float]]],
) -> int | None:
    """Return the index of the header row, or ``None`` if undetectable."""
    for idx, row in enumerate(rows):
        if _row_has_known_columns(row, min_matches=3):
            return idx
    for idx, row in enumerate(rows):
        cells = [text for _, text, _ in row if text.strip()]
        if len(cells) < 3:
            continue
        alpha_count = sum(1 for c in cells if _has_alpha(c))
        if alpha_count / len(cells) > _ALPHA_THRESHOLD:
            return idx
    for idx, row in enumerate(rows):
        cells = [text for _, text, _ in row if text.strip()]
        if not cells:
            continue
        alpha_count = sum(1 for c in cells if _has_alpha(c))
        if alpha_count / len(cells) > _ALPHA_THRESHOLD:
            return idx
    return None


def _build_dataframe(
    data_rows: list[list[tuple[list[list[float]], str, float]]],
    header_row: list[tuple[list[list[float]], str, float]] | None,
) -> pd.DataFrame:
    if header_row is not None:
        col_names = [text for _, text, _ in header_row]
    else:
        max_cols = max((len(r) for r in data_rows), default=0)
        col_names = [f"col_{i}" for i in range(max_cols)]

    records: list[dict[str, str | None]] = []
    for row in data_rows:
        cells = [text for _, text, _ in row]
        while len(cells) < len(col_names):
            cells.append(None)
        records.append(dict(zip(col_names, cells[: len(col_names)])))
    return pd.DataFrame(records)


class OcrReader(DataReader):
    """Read tabular data from images via EasyOCR."""

    def __init__(
        self,
        conf_threshold: float = 0.3,
        language: list[str] | None = None,
        row_tolerance: float = 0.6,
        header_rows: int | None = None,
        allowlist: str | None = None,
    ) -> None:
        self._conf_threshold = conf_threshold
        self._language = language or ["en"]
        self._row_tolerance = row_tolerance
        self._header_rows = header_rows
        self._allowlist = allowlist

    def supports(self, ext: str) -> bool:
        return ext.lower() in {".png", ".jpg", ".jpeg"}

    def read(self, path: Path, **kwargs: object) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        conf_th = kwargs.get("conf_threshold", self._conf_threshold)
        lang = kwargs.get("language", self._language)
        row_tol = kwargs.get("row_tolerance", self._row_tolerance)
        hdr_rows = kwargs.get("header_rows", self._header_rows)
        allowlist = kwargs.get("allowlist", self._allowlist)

        img = Image.open(path).convert("RGB")

        upscale = kwargs.get("ocr_upscale", False)
        if upscale:
            orig_w, orig_h = img.size
            target = max(orig_w, orig_h)
            if target < 2000:
                scale = 2000.0 / target
                img = img.resize(
                    (int(orig_w * scale), int(orig_h * scale)),
                    Image.LANCZOS,
                )

        img_array = np.array(img)
        reader = _get_easyocr(languages=lang, gpu=False)

        ocr_kwargs: dict[str, object] = {"detail": 1}
        if allowlist is not None:
            ocr_kwargs["allowlist"] = allowlist
        results: list[tuple[list[list[float]], str, float]] = reader.readtext(
            img_array, **ocr_kwargs  # type: ignore[arg-type]
        )

        if conf_th > 0:
            results = [r for r in results if r[2] >= conf_th]

        if hdr_rows == 0:
            rows = _group_by_rows(results, row_height_tolerance=row_tol)
            return _build_dataframe(rows, None)
        return _reconstruct_table_v3(results, row_height_tolerance=row_tol)


# ==============================================================================
# Reader factory
# ==============================================================================

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

_READERS: list[DataReader] | None = None


def _ensure_readers() -> list[DataReader]:
    global _READERS
    if _READERS is None:
        _READERS = [CsvReader(), ExcelReader()]
        try:
            _READERS.append(OcrReader())
        except ImportError:
            pass
    return _READERS


def detect_reader(path: Path) -> DataReader:
    """Select the appropriate reader for *path* based on its file extension."""
    ext = path.suffix.lower()
    for reader in _ensure_readers():
        if reader.supports(ext):
            return reader
    if ext in _IMAGE_EXTENSIONS:
        raise ValueError(
            f"No reader found for {path!r} (extension {ext!r}). "
            "Image files require easyocr. "
            "Install with: pip install matchaudit[ocr]"
        )
    raise ValueError(
        f"No reader found for {path!r} (extension {ext!r}). "
        "Supported: .csv, .xlsx, .xls"
    )


# ==============================================================================
# Comparison engine
# ==============================================================================


def _validate_input(
    source_df: pd.DataFrame,
    captured_df: pd.DataFrame,
    key_columns: list[str],
) -> None:
    if not key_columns:
        raise ValueError("At least one key column is required.")
    for name, df in [("source", source_df), ("captured", captured_df)]:
        missing = [col for col in key_columns if col not in df.columns]
        if missing:
            raise ValueError(
                f"Key columns {missing} not found in {name} DataFrame. "
                f"Available columns: {list(df.columns)}"
            )


def _make_key(row: pd.Series, key_columns: list[str]) -> Any:
    if len(key_columns) == 1:
        return row[key_columns[0]]
    return tuple(row[k] for k in key_columns)


def _serialize(val: Any) -> Any:
    if pd.isna(val):
        return None
    return val


def _values_differ(a: Any, b: Any) -> bool:
    if a is b:
        return False
    if a is None and b is None:
        return False
    if pd.isna(a) and pd.isna(b):
        return False
    try:
        return bool(a != b)
    except (ValueError, TypeError):
        return str(a) != str(b)


def _detect_shifts(
    source_df: pd.DataFrame,
    captured_df: pd.DataFrame,
    key_columns: list[str],
    missing_df: pd.DataFrame,
    extra_df: pd.DataFrame,
) -> list[RowShift]:
    shifted: list[RowShift] = []
    if missing_df.empty or extra_df.empty or len(missing_df) != len(extra_df):
        return shifted
    sort_cols = key_columns[:1]
    missing_sorted = missing_df.sort_values(by=sort_cols).reset_index(drop=True)
    extra_sorted = extra_df.sort_values(by=sort_cols).reset_index(drop=True)
    for i in range(len(missing_sorted)):
        miss_row = missing_sorted.iloc[i]
        extra_row = extra_sorted.iloc[i]
        key_val = _make_key(miss_row, key_columns)
        exp_pos = (
            int(miss_row.name) if isinstance(miss_row.name, (int, float)) else 0
        )
        act_pos = (
            int(extra_row.name) if isinstance(extra_row.name, (int, float)) else 0
        )
        shifted.append(
            RowShift(
                expected_position=exp_pos,
                actual_position=act_pos,
                key=key_val,
                surrounding_rows=(None, None),
            )
        )
    return shifted


def compare(
    source_df: pd.DataFrame,
    captured_df: pd.DataFrame,
    key_columns: list[str],
) -> ComparisonResult:
    """Compare two DataFrames row by row using *key_columns* as row identifiers."""
    _validate_input(source_df, captured_df, key_columns)

    # Separate rows with NaN key values
    source_null_mask = source_df[key_columns].isna().any(axis=1)
    captured_null_mask = captured_df[key_columns].isna().any(axis=1)
    source_null_rows = source_df[source_null_mask].copy()
    captured_null_rows = captured_df[captured_null_mask].copy()
    source_valid = source_df[~source_null_mask].copy()
    captured_valid = captured_df[~captured_null_mask].copy()

    for col in key_columns:
        source_valid[col] = source_valid[col].astype(str)
        captured_valid[col] = captured_valid[col].astype(str)

    merged = pd.merge(
        source_valid,
        captured_valid,
        on=key_columns,
        how="outer",
        indicator=True,
        suffixes=("_expected", "_actual"),
    )

    matched_mask = merged["_merge"] == "both"
    missing_mask = merged["_merge"] == "left_only"
    extra_mask = merged["_merge"] == "right_only"
    matched_count = int(matched_mask.sum())

    value_columns = [
        col for col in source_df.columns if col not in key_columns
    ]

    mismatched_rows: list[RowDiff] = []
    matched_subset = merged[matched_mask]
    for _, row in matched_subset.iterrows():
        for col in value_columns:
            exp_sfx = f"{col}_expected"
            expected_col = exp_sfx if exp_sfx in matched_subset.columns else col
            act_sfx = f"{col}_actual"
            actual_col = act_sfx if act_sfx in matched_subset.columns else col
            expected_val = row[expected_col]
            actual_val = row[actual_col]
            if _values_differ(expected_val, actual_val):
                key_val = _make_key(row, key_columns)
                idx = int(row.name) if isinstance(row.name, (int, float)) else 0
                mismatched_rows.append(
                    RowDiff(
                        index=idx,
                        key=key_val,
                        column=col,
                        expected=_serialize(expected_val),
                        actual=_serialize(actual_val),
                    )
                )

    missing_rows: list[RowDiff] = []
    missing_subset = merged[missing_mask]
    for _, row in missing_subset.iterrows():
        idx = int(row.name) if isinstance(row.name, (int, float)) else 0
        missing_rows.append(
            RowDiff(
                index=idx,
                key=_make_key(row, key_columns),
                column=None,
                expected="(present in source)",
                actual="(missing in captured)",
            )
        )

    extra_rows: list[RowDiff] = []
    extra_subset = merged[extra_mask]
    for _, row in extra_subset.iterrows():
        idx = int(row.name) if isinstance(row.name, (int, float)) else 0
        extra_rows.append(
            RowDiff(
                index=idx,
                key=_make_key(row, key_columns),
                column=None,
                expected="(missing in source)",
                actual="(extra in captured)",
            )
        )

    # Append rows with NaN key columns
    for _, row in source_null_rows.iterrows():
        idx = int(row.name) if isinstance(row.name, (int, float)) else 0
        missing_rows.append(
            RowDiff(
                index=idx,
                key=_make_key(row, key_columns),
                column=None,
                expected="(present in source)",
                actual="(missing in captured — key is empty)",
            )
        )
    for _, row in captured_null_rows.iterrows():
        idx = int(row.name) if isinstance(row.name, (int, float)) else 0
        extra_rows.append(
            RowDiff(
                index=idx,
                key=_make_key(row, key_columns),
                column=None,
                expected="(missing in source)",
                actual="(extra in captured — key is empty)",
            )
        )

    shifted_rows = _detect_shifts(
        source_df, captured_df, key_columns, missing_subset, extra_subset
    )

    total_expected = len(source_df)
    total_captured = len(captured_df)
    max_total = max(total_expected, total_captured)
    match_rate = matched_count / max_total if max_total > 0 else 1.0

    has_misalignment = bool(mismatched_rows or missing_rows or extra_rows or shifted_rows)
    if not has_misalignment:
        severity: str = "ok"
    elif missing_rows or extra_rows:
        severity = "critical"
    else:
        severity = "warning"

    stats = ComparisonStats(
        total_expected=total_expected,
        total_captured=total_captured,
        match_rate=round(match_rate, 4),
        has_misalignment=has_misalignment,
        severity=severity,  # type: ignore[arg-type]
    )

    status: str = "match" if not has_misalignment else "mismatch"

    return ComparisonResult(
        status=status,  # type: ignore[arg-type]
        matched_rows=matched_count,
        mismatched_rows=mismatched_rows,
        missing_rows=missing_rows,
        extra_rows=extra_rows,
        shifted_rows=shifted_rows,
        stats=stats,
    )


# ==============================================================================
# CLI
# ==============================================================================

import click  # noqa: E402


_KEY_COLUMN_CANDIDATES = [
    "id",
    "codigo",
    "nombre",
    "name",
    "code",
    "email",
    "username",
    "usuario",
    "pais",
    "slug",
    "reference",
    "referencia",
    "transaction_id",
    "documento",
    "numero",
    "nro",
]

_IMAGE_EXTENSIONS_CLI = {".png", ".jpg", ".jpeg"}


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_EXTENSIONS_CLI


def _auto_detect_key_columns(df_a: pd.DataFrame, df_b: pd.DataFrame) -> list[str] | None:
    common = set(df_a.columns) & set(df_b.columns)
    for candidate in _KEY_COLUMN_CANDIDATES:
        if candidate in common:
            return [candidate]
    for col in common:
        if df_a[col].nunique() == len(df_a) or df_b[col].nunique() == len(df_b):
            return [col]
    return None


# -- Batch helpers --------------------------------------------------------


def _find_batch_pairs(
    source_dir: Path,
    captured_dir: Path,
    prefix_match: bool = False,
) -> tuple[list[tuple[str, Path, Path]], set[str], set[str]]:
    source_extensions = {".csv", ".xlsx", ".xls"}
    captured_extensions = source_extensions | {".png", ".jpg", ".jpeg"}

    sources: dict[str, Path] = {}
    for f in source_dir.iterdir():
        if f.is_file() and f.suffix.lower() in source_extensions:
            sources.setdefault(f.stem, f)

    captures: dict[str, Path] = {}
    for f in captured_dir.iterdir():
        if f.is_file() and f.suffix.lower() in captured_extensions:
            captures.setdefault(f.stem, f)

    matched_captures: set[str] = set()
    matched_sources: set[str] = set()
    pairs: list[tuple[str, Path, Path]] = []

    if prefix_match:
        for src_stem in sorted(sources):
            prefix = src_stem + "_"
            for cap_stem, cap_path in sorted(captures.items()):
                if cap_stem.startswith(prefix):
                    pairs.append((src_stem, sources[src_stem], cap_path))
                    matched_captures.add(cap_stem)
                    matched_sources.add(src_stem)
        unmatched_src = set(sources) - matched_sources
        unmatched_cap = set(captures) - matched_captures
    else:
        common = set(sources) & set(captures)
        pairs = [(stem, sources[stem], captures[stem]) for stem in sorted(common)]
        unmatched_src = set(sources) - common
        unmatched_cap = set(captures) - common

    return pairs, unmatched_src, unmatched_cap


def _warn_unmatched(
    console: Any,
    side: str,
    stems: list[str],
    directory: Path,
) -> None:
    console.print(
        f"[yellow]⚠️  {len(stems)} archivo(s) en {directory.name} "
        f"(#{side}) no tienen contraparte:[/yellow]"
    )
    for name in stems:
        console.print(f"   {name}")


def _render_batch_summary(
    console: Any,
    results: list[tuple[str, ComparisonResult]],
) -> None:
    from rich.table import Table

    if not results:
        console.print("[yellow]No se produjeron resultados.[/yellow]")
        return

    summary = Table(title="Resultado Consolidado — Comparación por Lote")
    summary.add_column("Archivo", style="bold")
    summary.add_column("Estado", no_wrap=True)
    summary.add_column("Match Rate")
    summary.add_column("Esperadas")
    summary.add_column("Capturadas")
    summary.add_column("Coinciden")
    summary.add_column("Diferencias")
    summary.add_column("Faltantes")
    summary.add_column("Sobrantes")

    ok_count = 0
    total_pairs = len(results)

    for stem, result in results:
        status = result.status
        emoji = "✅" if status == "match" else "❌"
        rate = f"{result.stats.match_rate:.1%}" if result.stats else "-"
        exp = str(result.stats.total_expected) if result.stats else "-"
        cap = str(result.stats.total_captured) if result.stats else "-"
        matched = str(result.matched_rows)
        diffs = str(len(result.mismatched_rows))
        missing = str(len(result.missing_rows))
        extra = str(len(result.extra_rows))
        summary.add_row(
            stem, f"{emoji} {status.upper()}", rate, exp, cap,
            matched, diffs, missing, extra,
        )
        if status == "match":
            ok_count += 1

    console.print(summary)
    console.print(
        f"\n[bold]{ok_count}/{total_pairs}[/bold] archivos OK, "
        f"[bold]{total_pairs - ok_count}[/bold] con diferencias\n"
    )

    for stem, result in results:
        if result.status == "match":
            continue
        console.rule(f"[red]{stem}[/red]")
        render_comparison(result)


# -- Click commands -------------------------------------------------------


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """MatchAudit: data validation and reconciliation for audit teams."""


@main.command()
@click.option(
    "--source",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to the source data file (.csv / .xlsx / .png).",
)
@click.option(
    "--captured",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to the captured data file (.csv / .xlsx / .png).",
)
@click.option(
    "--key-columns",
    default=None,
    help="Comma-separated key column(s). Auto-detected when omitted.",
)
@click.option(
    "--label-column",
    default=None,
    help="Column for ordering/range slicing (optional).",
)
@click.option(
    "--start",
    default=None,
    type=str,
    help="Start label for range slicing, inclusive (optional).",
)
@click.option(
    "--end",
    default=None,
    type=str,
    help="End label for range slicing, inclusive (optional).",
)
@click.option(
    "--output",
    default=None,
    type=click.Choice(["json"]),
    help="Output format (default: Rich console).",
)
@click.option(
    "--ocr-language",
    default="es,en",
    show_default=True,
    help="OCR language(s), comma-separated.",
)
@click.option(
    "--ocr-conf-threshold",
    default=0.0,
    type=float,
    show_default=True,
    help="OCR confidence threshold (0.0-1.0).",
)
@click.option(
    "--ocr-upscale",
    is_flag=True,
    default=False,
    help="Upscale image before OCR (slower, better small-text detection).",
)
def compare_command(
    source: Path,
    captured: Path,
    key_columns: str | None,
    label_column: str | None,
    start: str | None,
    end: str | None,
    output: str | None,
    ocr_language: str,
    ocr_conf_threshold: float,
    ocr_upscale: bool,
) -> None:
    """Compare two datasets and report differences."""
    try:
        needs_ocr = _is_image(source) or _is_image(captured)
        if needs_ocr:
            try:
                import easyocr  # noqa: F401
            except ImportError:
                raise click.ClickException(
                    "EasyOCR is required for image files. "
                    "Install with: pip install matchaudit[ocr]"
                )

        source_reader = detect_reader(source)
        captured_reader = detect_reader(captured)

        if needs_ocr:
            ocr_kwargs: dict[str, object] = {
                "language": [lang.strip() for lang in ocr_language.split(",")],
                "conf_threshold": ocr_conf_threshold,
                "ocr_upscale": ocr_upscale,
            }

            def _read_with_ocr(reader: Any, path: Path) -> pd.DataFrame:
                if isinstance(reader, OcrReader):
                    return reader.read(path, **ocr_kwargs)
                return reader.read(path)

            source_df = _read_with_ocr(source_reader, source)
            captured_df = _read_with_ocr(captured_reader, captured)
        else:
            source_df = source_reader.read(source)
            captured_df = captured_reader.read(captured)

        keys: list[str]
        if key_columns:
            keys = [k.strip() for k in key_columns.split(",")]
        else:
            detected = _auto_detect_key_columns(source_df, captured_df)
            if detected:
                keys = detected
                click.echo(f"ℹ️  Key column auto-detectada: {detected[0]}")
            else:
                raise click.ClickException(
                    "Could not auto-detect key columns. "
                    "Use --key-columns to specify them."
                )

        if label_column is not None and start is not None and end is not None:
            source_df = extract_control_point(source_df, label_column, start, end)
            captured_df = extract_control_point(captured_df, label_column, start, end)

        result = compare(source_df, captured_df, keys)
        render_comparison(result, output_format=output)

    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))


@main.command()
@click.option(
    "--source-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory with source files (.csv / .xlsx).",
)
@click.option(
    "--captured-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory with captured files (.png / .jpg / .jpeg).",
)
@click.option(
    "--key-columns",
    default=None,
    help="Comma-separated key column(s). Auto-detected when omitted.",
)
@click.option(
    "--ocr-language",
    default="es,en",
    show_default=True,
    help="OCR language(s), comma-separated.",
)
@click.option(
    "--ocr-conf-threshold",
    default=0.0,
    type=float,
    show_default=True,
    help="OCR confidence threshold (0.0-1.0).",
)
@click.option(
    "--prefix-match",
    is_flag=True,
    default=False,
    help="Match captures by prefix: 'usuarios.csv' matches both "
    "'usuarios_primer.png' and 'usuarios_ultimo.png'.",
)
@click.option(
    "--ocr-upscale",
    is_flag=True,
    default=False,
    help="Upscale images before OCR (slower, better small-text detection).",
)
def batch_compare(
    source_dir: Path,
    captured_dir: Path,
    key_columns: str | None,
    prefix_match: bool,
    ocr_language: str,
    ocr_conf_threshold: float,
    ocr_upscale: bool,
) -> None:
    """Compare all source files against corresponding captures, matched by filename."""
    from rich.console import Console

    console = Console()

    pairs, unmatched_src, unmatched_cap = _find_batch_pairs(
        source_dir, captured_dir, prefix_match=prefix_match
    )

    if not pairs:
        msg = "No matching file pairs found between directories."
        if unmatched_src:
            msg += f"\n  Unmatched source files: {', '.join(sorted(unmatched_src))}"
        if unmatched_cap:
            msg += f"\n  Unmatched captured files: {', '.join(sorted(unmatched_cap))}"
        raise click.ClickException(msg)

    if unmatched_src:
        _warn_unmatched(console, "source", sorted(unmatched_src), source_dir)
    if unmatched_cap:
        _warn_unmatched(console, "captured", sorted(unmatched_cap), captured_dir)

    ocr_reader = None
    if any(_is_image(cap) for _, _, cap in pairs):
        try:
            import easyocr  # noqa: F401
            ocr_reader = OcrReader()
        except ImportError:
            raise click.ClickException(
                "EasyOCR is required for image files. "
                "Install with: pip install matchaudit[ocr]"
            )

    ocr_kwargs: dict[str, object] = {
        "language": [lang.strip() for lang in ocr_language.split(",")],
        "conf_threshold": ocr_conf_threshold,
        "ocr_upscale": ocr_upscale,
    }

    results: list[tuple[str, ComparisonResult]] = []

    for stem, src_path, cap_path in pairs:
        try:
            source_reader = detect_reader(src_path)
            source_df = source_reader.read(src_path)

            if ocr_reader is not None and _is_image(cap_path):
                captured_df = ocr_reader.read(cap_path, **ocr_kwargs)
            else:
                captured_df = detect_reader(cap_path).read(cap_path)

            keys: list[str]
            if key_columns:
                keys = [k.strip() for k in key_columns.split(",")]
            else:
                detected = _auto_detect_key_columns(source_df, captured_df)
                if detected:
                    keys = detected
                else:
                    click.echo(f"⚠️  {stem}: no se pudo auto-detectar key column, se saltea")
                    continue

            result = compare(source_df, captured_df, keys)
            results.append((stem, result))

        except Exception as exc:
            click.echo(f"❌  {stem}: error — {exc}")
            continue

    _render_batch_summary(console, results)


@main.command()
def validate() -> None:
    """Validate a control point against source data."""
    click.echo("validate: not yet implemented")


# ==============================================================================
# Main entry point
# ==============================================================================

if __name__ == "__main__":
    main()
