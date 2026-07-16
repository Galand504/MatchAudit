"""OCR reader — extracts tabular data from images via EasyOCR.

Usage::

    reader = OcrReader()
    df = reader.read(Path("capture.png"))
    df = reader.read(Path("capture.jpg"), conf_threshold=0.5)

Requires ``easyocr`` and ``pillow`` (install via ``pip install matchaudit[ocr]``).
"""

from __future__ import annotations

import warnings
from pathlib import Path

from pandas import DataFrame

from matchaudit.readers import DataReader

# Suppress noisy PyTorch/EasyOCR deprecation warnings that the user cannot
# act on — these come from inside torch's quantized module internals.
warnings.filterwarnings("ignore", message="torch.quantize_per_tensor")
warnings.filterwarnings("ignore", message="torch.ao.quantization is deprecated")
warnings.filterwarnings("ignore", message="pin_memory.*argument is set as true")

# ---------------------------------------------------------------------------
# Lazy optional dependencies — each guarded so the module loads gracefully
# when not installed (CI, minimal environments).
# ---------------------------------------------------------------------------

_OCR_INSTANCE: object | None = None

_MISSING_DEPS: list[str] = []

try:
    import numpy as np  # noqa: F811
except ImportError:
    np = None  # type: ignore[assignment]
    _MISSING_DEPS.append("numpy")

try:
    from PIL import Image  # noqa: F811
except ImportError:
    Image = None  # type: ignore[assignment]
    _MISSING_DEPS.append("pillow")

try:
    import easyocr  # noqa: F811

    _HAS_EASYOCR = True
except ImportError:
    _HAS_EASYOCR = False


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


# ---------------------------------------------------------------------------
# Row-grouping helpers
# ---------------------------------------------------------------------------

def _bbox_y_center(bbox: list[list[float]]) -> float:
    """Return the vertical midpoint of a bounding box.

    *bbox* is a quadrilateral ``[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]`` where
    ``(x1,y1)`` is top-left and ``(x3,y3)`` is bottom-right.
    """
    return (bbox[0][1] + bbox[2][1]) / 2.0


def _bbox_height(bbox: list[list[float]]) -> float:
    """Return the height of a bounding box."""
    return abs(bbox[2][1] - bbox[0][1])


def _bbox_x_center(bbox: list[list[float]]) -> float:
    """Return the horizontal midpoint of a bounding box."""
    return (bbox[0][0] + bbox[2][0]) / 2.0


def _bbox_x_start(bbox: list[list[float]]) -> float:
    """Return the left X coordinate of a bounding box."""
    return bbox[0][0]


def _bbox_x_end(bbox: list[list[float]]) -> float:
    """Return the right X coordinate of a bounding box."""
    return bbox[2][0]


def _group_by_rows(
    results: list[tuple[list[list[float]], str, float]],
    row_height_tolerance: float = 0.6,
) -> list[list[tuple[list[list[float]], str, float]]]:
    """Group EasyOCR detections into rows by Y-centre proximity.

    Parameters
    ----------
    results:
        EasyOCR ``readtext()`` output — list of ``(bbox, text, confidence)``
        tuples.
    row_height_tolerance:
        Fraction of the median row height used as the Y-centre grouping
        threshold.  Higher values merge nearby rows.

    Returns
    -------
    list[list[...]]:
        Detections grouped by row, ordered top-to-bottom.  Each inner list is
        sorted left-to-right by X-centre.
    """
    if not results:
        return []

    # Attach derived metrics
    items: list[tuple[float, float, float, list[list[float]], str, float]] = []
    for bbox, text, conf in results:
        yc = _bbox_y_center(bbox)
        h = _bbox_height(bbox)
        xc = _bbox_x_center(bbox)
        items.append((yc, h, xc, bbox, text, conf))

    # Sort by Y-centre
    items.sort(key=lambda t: t[0])

    # Estimate median row height for tolerance calculation
    heights = [h for _, h, _, _, _, _ in items]
    median_height = float(np.median(heights)) if heights else 20.0
    y_tolerance = median_height * row_height_tolerance

    # Cluster
    groups: list[list[tuple[list[list[float]], str, float]]] = []
    current_group: list[tuple[float, list[list[float]], str, float]] = []
    current_y = items[0][0]

    for yc, _h, xc, bbox, text, conf in items:
        if abs(yc - current_y) > y_tolerance:
            # Flush current group
            current_group.sort(key=lambda t: t[0])  # sort by x_centre
            groups.append([(b, t, c) for _, b, t, c in current_group])
            current_group = []
            current_y = yc
        current_group.append((xc, bbox, text, conf))

    if current_group:
        current_group.sort(key=lambda t: t[0])
        groups.append([(b, t, c) for _, b, t, c in current_group])

    return groups


# ---------------------------------------------------------------------------
# V2: Column-boundary-aware reconstruction
# ---------------------------------------------------------------------------

# DEPRECATED: _get_column_boundaries and _assign_to_columns removed in favor
# of _reconstruct_table_v3 which uses X-gap clustering.


# ---------------------------------------------------------------------------
# V3: X-gap column clustering (robust table reconstruction)
# ---------------------------------------------------------------------------

def _estimate_char_width(
    row: list[tuple[list[list[float]], str, float]],
) -> float:
    """Estimate average character width from a row's detections."""
    widths: list[float] = []
    for bbox, text, _ in row:
        w = _bbox_x_end(bbox) - _bbox_x_start(bbox)
        tl = len(text.strip())
        if tl > 1:
            widths.append(w / tl)
    return float(np.median(widths)) if widths else 10.0


def _cluster_row_by_x_gap(
    row: list[tuple[list[list[float]], str, float]],
    gap_factor: float = 4.0,
) -> list[list[tuple[list[list[float]], str, float]]]:
    """Cluster detections within a row into cells by X-gap proximity.

    Detections whose X-gap is smaller than ``char_width * gap_factor`` are
    merged into a single cell (multi-word value).  Larger gaps separate
    columns.

    Returns a list of clusters (each cluster = one cell), ordered left-to-right.
    """
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
            # Same column — merge
            current.append(sorted_row[i])
        else:
            # New column
            clusters.append(current)
            current = [sorted_row[i]]

    if current:
        clusters.append(current)

    return clusters


def _get_column_names_from_header(
    header_cells: list[list[tuple[list[list[float]], str, float]]],
    column_spread: float = 0.5,
) -> list[tuple[str, float, float, float]]:
    """Extract column names and X-boundaries from clustered header cells.

    Returns ``(col_name, x_start, x_end, x_center)`` for each cell.
    Boundaries extend to midpoint between adjacent columns.

    If a cluster contains multiple detections that each match a known
    column name, it is split into individual columns (handles columns
    with very small X-gaps like ``id_revista`` next to ``nombre``).
    """
    # First pass: split clusters that contain multiple known column names
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

    # Sort by X position
    expanded.sort(key=lambda c: min(_bbox_x_start(b) for b, _, _ in c))

    columns: list[tuple[str, float, float, float]] = []
    n = len(expanded)

    # Estimate image width from the rightmost detection
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
            x_end += est_width * 0.12  # ~12% of estimated width for last col

        if i > 0:
            prev_end = max(_bbox_x_end(b) for b, _, _ in expanded[i - 1])
            x_start = (x_start + prev_end) / 2.0
        else:
            x_start = max(0, x_start - est_width * 0.02)  # ~2% left margin

        columns.append((text.lower(), x_start, x_end, x_center))

    # Normalize column names through OCR alias map
    columns = [
        (_OCR_HEADER_ALIASES.get(name, name), xs, xe, xc)
        for name, xs, xe, xc in columns
    ]

    return columns


# ---------------------------------------------------------------------------
# Text post-processing
# ---------------------------------------------------------------------------

import re as _re

_DATE_TIME_FIX = _re.compile(r"(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}:\d{2})")
"""Matches ``YYYY-MM-DDHH:MM:SS`` — OCR often merges the space out."""


def _postprocess_text(text: str) -> str:
    """Clean up common OCR artifacts in a cell's text."""
    if not text:
        return text
    result = text.strip()
    # Fix merged date/time: 2026-05-3119:57:08 → 2026-05-31 19:57:08
    result = _DATE_TIME_FIX.sub(r"\1 \2", result)
    # Normalise whitespace (collapses multiple spaces)
    result = _re.sub(r" {2,}", " ", result)
    # Strip leading/trailing punctuation (except decimal points)
    result = _re.sub(r"^[^\w\d]+", "", result)
    result = _re.sub(r"[^\w\d]+$", "", result)
    return result


def _reconstruct_table_v3(
    results: list[tuple[list[list[float]], str, float]],
    row_height_tolerance: float = 0.6,
    gap_factor: float = 3.0,
) -> DataFrame:
    """Reconstruct a table using X-gap column clustering.

    Unlike V2, this algorithm does NOT depend on hardcoded column names or
    sidebar position heuristics.  It works on any screenshot by:

    1. Grouping detections by Y (rows).
    2. Detecting the header row via known column names or alpha-ratio.
    3. Clustering each header cell by X-gap → derives column boundaries.
    4. Filtering columns to only keep known-data columns.
    5. Clustering each data row by X-gap → assigns cells to columns.
    6. Merging fragment rows that fill complementary columns.
    7. Filtering empty/footer rows.
    """
    rows = _group_by_rows(results, row_height_tolerance=row_height_tolerance)
    if not rows:
        return DataFrame()

    # Detect header row
    header_idx = _detect_header(rows)
    if header_idx is None:
        return _build_dataframe(rows, None)

    header_row = rows[header_idx]
    data_rows = rows[header_idx + 1:]

    if not data_rows:
        return DataFrame()

    # Cluster header into cells → derive column boundaries
    header_cells = _cluster_row_by_x_gap(header_row, gap_factor=gap_factor)
    all_columns = _get_column_names_from_header(header_cells)

    if not all_columns:
        return _build_dataframe(data_rows, header_row)

    # Filter to only keep known-data columns (removes sidebar/UI elements)
    # A column is kept if any word in its name matches a known column name,
    # or if the name contains common DB column patterns like "_".
    data_columns = [
        (name, xs, xe, xc) for name, xs, xe, xc in all_columns
        if any(kw == name for kw in _KNOWN_COLUMN_NAMES)
        or any(kw in name.split() for kw in _KNOWN_COLUMN_NAMES)
        or "_" in name  # underscore → DB column naming convention
    ]

    # If no columns matched known names, use all columns
    if not data_columns:
        data_columns = all_columns

    col_names = [c[0] for c in data_columns]

    # Process each data row, merging adjacent fragments when bold text
    # ends up in a separate Y-group from the rest of its row.
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
                continue  # post-processing may have stripped it entirely
            cell_xc = _bbox_x_center(_cell[0][0])
            # Only consider columns whose X-range actually contains the cell.
            # Using min(…, default=None) with float("inf") is incorrect because
            # min() returns the FIRST element when all keys are equal — so a
            # cell far outside every column would be spuriously assigned to the
            # first data column.
            candidates = [
                c for c in data_columns if c[1] <= cell_xc <= c[2]
            ]
            if not candidates:
                continue
            best_col = min(candidates, key=lambda c: abs(cell_xc - c[3]))
            _rec[best_col[0]] = cell_text
        return _rec

    min_data_cols = max(len(col_names) // 2, 2)  # at least half the columns
    records: list[dict[str, str | None]] = []

    i = 0
    while i < len(data_rows):
        row = data_rows[i]
        cells = _cluster_row_by_x_gap(row, gap_factor=gap_factor)
        record = _assign_cells(cells)
        vals = [v for v in record.values() if v is not None]

        # Try merging with the next row if this row is too sparse and
        # the next row fills complementary (non-overlapping) columns.
        merged = False
        if len(vals) < min_data_cols and i + 1 < len(data_rows):
            next_cells = _cluster_row_by_x_gap(data_rows[i + 1], gap_factor=gap_factor)
            next_record = _assign_cells(next_cells)
            next_vals = [v for v in next_record.values() if v is not None]

            # Only merge if they fill different columns (no overlap)
            has_overlap = any(
                record[c] is not None and next_record[c] is not None
                for c in col_names
            )
            combined_vals = vals + next_vals
            if not has_overlap and len(combined_vals) >= min_data_cols:
                # Merge: later columns override earlier for same col
                merged_rec = {**record}
                for c in col_names:
                    if next_record[c] is not None:
                        merged_rec[c] = next_record[c]
                record = merged_rec
                vals = [v for v in record.values() if v is not None]
                merged = True
                i += 1  # skip the merged row

        # Only keep rows with enough real data columns
        if len(vals) >= min_data_cols:
            # Skip pagination/footer rows.  Must be strict to avoid matching
            # legitimate content such as "Journal of Latin American Studies".
            has_footer = any(
                v and _re.search(
                    r"(?:^showing|rows per page|page \d+ of|\d+-\d+ of )",
                    v.lower(),
                )
                for v in vals
            )
            if not has_footer:
                # Deduplicate — skip if identical record already appended
                if record not in records:
                    records.append(record)

        i += 1

    if not records:
        return DataFrame()

    return DataFrame(records)


# ---------------------------------------------------------------------------
# OcrReader — DataReader implementation
# ---------------------------------------------------------------------------
# Header detection & DataFrame builder
# ---------------------------------------------------------------------------

_ALPHA_THRESHOLD = 0.4  # fraction of alpha cells needed to classify as header

# Common column names in database/audit tables — used for header detection
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

# OCR-to-real column name mapping for common misreads
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


def _has_alpha(text: str) -> bool:
    """Return ``True`` if *text* contains at least one alphabetic character."""
    return any(ch.isalpha() for ch in text)


def _is_numeric_cell(text: str) -> bool:
    """Return ``True`` if *text* looks like a number or date fragment."""
    stripped = text.strip().replace(",", "").replace(".", "").replace("-", "")
    return stripped.isdigit() or text == ""


def _row_has_known_columns(
    row: list[tuple[list[list[float]], str, float]],
    min_matches: int = 3,
) -> bool:
    """Check if a row contains known column names.

    Returns True if at least *min_matches* cell texts match known column
    names (case-insensitive, stripped).
    """
    matches = 0
    for _, text, _ in row:
        normalized = text.strip().lower()
        if normalized in _KNOWN_COLUMN_NAMES:
            matches += 1
    return matches >= min_matches


def _detect_header(
    rows: list[list[tuple[list[list[float]], str, float]]],
) -> int | None:
    """Return the index of the header row, or ``None`` if undetectable.

    Detection strategy (in order of priority):
    1. Row with known column names (id, nombre, tipo, issn, etc.)
    2. Row with many columns (>3) and mostly alphabetic content
    3. First row with >40% alphabetic content (fallback)
    """
    # Strategy 1: Look for known column names
    for idx, row in enumerate(rows):
        if _row_has_known_columns(row, min_matches=3):
            return idx

    # Strategy 2: Row with many columns and mostly alphabetic
    for idx, row in enumerate(rows):
        cells = [text for _, text, _ in row if text.strip()]
        if len(cells) < 3:
            continue
        alpha_count = sum(1 for c in cells if _has_alpha(c))
        if alpha_count / len(cells) > _ALPHA_THRESHOLD:
            return idx

    # Strategy 3: First row with >40% alphabetic (fallback)
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
) -> DataFrame:
    """Build a ``pandas.DataFrame`` from row-grouped OCR detections.

    Parameters
    ----------
    data_rows:
        Row groups *after* the header (each inner list is a row of cells).
    header_row:
        Optional header row used for column names.  When ``None``, generic
        ``col_0`` … ``col_N`` names are assigned.

    Returns
    -------
    DataFrame
    """
    # Determine column names
    if header_row is not None:
        col_names = [text for _, text, _ in header_row]
    else:
        # Infer max column count from data
        max_cols = max((len(r) for r in data_rows), default=0)
        col_names = [f"col_{i}" for i in range(max_cols)]

    # Build rows
    records: list[dict[str, str | None]] = []
    for row in data_rows:
        cells = [text for _, text, _ in row]
        # Pad shorter rows with None
        while len(cells) < len(col_names):
            cells.append(None)
        records.append(dict(zip(col_names, cells[: len(col_names)])))

    return DataFrame(records)


# ---------------------------------------------------------------------------
# OcrReader — DataReader implementation
# ---------------------------------------------------------------------------

class OcrReader(DataReader):
    """Read tabular data from images via EasyOCR.

    Parameters
    ----------
    conf_threshold:
        Minimum confidence score (0–1) to keep a detection.  Detections below
        this threshold are discarded.
    language:
        Language(s) passed to EasyOCR (default ``["en"]``).
    row_tolerance:
        Fraction of median row height used for Y-centre grouping.
    header_rows:
        Explicit number of header rows.  ``None`` (default) means auto-detect.
    allowlist:
        Optional string of allowed characters passed to EasyOCR (applied at
        the engine level).
    """

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

    # ------------------------------------------------------------------
    # DataReader interface
    # ------------------------------------------------------------------

    def supports(self, ext: str) -> bool:
        """Return ``True`` for ``.png``, ``.jpg``, and ``.jpeg``."""
        return ext.lower() in {".png", ".jpg", ".jpeg"}

    def read(self, path: Path, **kwargs: object) -> DataFrame:
        """Read an image file and return a DataFrame.

        Parameters
        ----------
        path:
            Path to a ``.png``, ``.jpg``, or ``.jpeg`` file.
        **kwargs:
            Override any constructor parameter at call time:
            ``conf_threshold``, ``language``, ``row_tolerance``,
            ``header_rows``, ``allowlist``.

        Returns
        -------
        DataFrame
            Tabular data reconstructed from OCR detections.

        Raises
        ------
        FileNotFoundError
            When *path* does not exist.
        ImportError
            When EasyOCR is not installed.
        """
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        if _MISSING_DEPS:
            raise ImportError(
                "Missing optional dependencies for OCR: "
                f"{', '.join(_MISSING_DEPS)}. "
                "Install with: pip install matchaudit[ocr]"
            )

        # Merge call-time kwargs with constructor defaults
        conf_th = kwargs.get("conf_threshold", self._conf_threshold)
        lang = kwargs.get("language", self._language)
        row_tol = kwargs.get("row_tolerance", self._row_tolerance)
        hdr_rows = kwargs.get("header_rows", self._header_rows)
        allowlist = kwargs.get("allowlist", self._allowlist)

        # Load image
        img = Image.open(path).convert("RGB")

        # Upscale image when requested (better small-text detection at
        # the cost of slower OCR).  Off by default for speed.
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

        # Obtain EasyOCR reader (lazy singleton)
        reader = _get_easyocr(languages=lang, gpu=False)

        # Run OCR
        ocr_kwargs: dict[str, object] = {"detail": 1}
        if allowlist is not None:
            ocr_kwargs["allowlist"] = allowlist
        results: list[tuple[list[list[float]], str, float]] = reader.readtext(
            img_array, **ocr_kwargs  # type: ignore[arg-type]
        )

        # Filter by confidence
        if conf_th > 0:
            results = [r for r in results if r[2] >= conf_th]

        # Use V3 X-gap-clustering reconstruction
        if hdr_rows == 0:
            rows = _group_by_rows(results, row_height_tolerance=row_tol)
            return _build_dataframe(rows, None)
        return _reconstruct_table_v3(results, row_height_tolerance=row_tol)
