"""OCR reader — extracts tabular data from images via EasyOCR.

Usage::

    reader = OcrReader()
    df = reader.read(Path("capture.png"))
    df = reader.read(Path("capture.jpg"), conf_threshold=0.5)

Requires ``easyocr`` and ``pillow`` (install via ``pip install matchaudit[ocr]``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pandas import DataFrame
from PIL import Image

from matchaudit.readers import DataReader

# ---------------------------------------------------------------------------
# Lazy EasyOCR singleton
# ---------------------------------------------------------------------------

_OCR_INSTANCE: object | None = None

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
# Header detection & DataFrame builder
# ---------------------------------------------------------------------------

_ALPHA_THRESHOLD = 0.4  # fraction of alpha cells needed to classify as header


def _has_alpha(text: str) -> bool:
    """Return ``True`` if *text* contains at least one alphabetic character."""
    return any(ch.isalpha() for ch in text)


def _is_numeric_cell(text: str) -> bool:
    """Return ``True`` if *text* looks like a number or date fragment."""
    stripped = text.strip().replace(",", "").replace(".", "").replace("-", "")
    return stripped.isdigit() or text == ""


def _detect_header(
    rows: list[list[tuple[list[list[float]], str, float]]],
) -> int | None:
    """Return the index of the header row, or ``None`` if undetectable.

    The header is heuristically identified as the *first* row where more than
    ``_ALPHA_THRESHOLD`` (40 %) of non-empty cells contain alphabetic
    characters — a strong signal that the row contains column labels rather
    than data values.
    """
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

        # Merge call-time kwargs with constructor defaults
        conf_th = kwargs.get("conf_threshold", self._conf_threshold)
        lang = kwargs.get("language", self._language)
        row_tol = kwargs.get("row_tolerance", self._row_tolerance)
        hdr_rows = kwargs.get("header_rows", self._header_rows)
        allowlist = kwargs.get("allowlist", self._allowlist)

        # Load image
        img = Image.open(path).convert("RGB")
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

        # Group into rows by Y-centre proximity
        rows = _group_by_rows(results, row_height_tolerance=row_tol)

        if not rows:
            return DataFrame()

        # Determine header
        if hdr_rows is not None:
            # Explicit row count
            header = rows[:hdr_rows]
            data = rows[hdr_rows:]
        else:
            idx = _detect_header(rows)
            if idx is not None:
                header = [rows[idx]]
                data = rows[idx + 1 :]
            else:
                header = None
                data = rows

        # Build DataFrame
        header_row = header[0] if header else None
        return _build_dataframe(data, header_row)
