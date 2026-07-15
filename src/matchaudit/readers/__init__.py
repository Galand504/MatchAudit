"""Data source import adapters — reader abstraction and factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pandas import DataFrame


class DataReader(ABC):
    """Abstract interface for all data source readers.

    Implementations read from a specific format and return a ``DataFrame``.
    Each reader declares which file extensions it supports via ``supports()``.
    """

    @abstractmethod
    def read(self, path: Path, **kwargs: object) -> DataFrame:
        """Read a data source and return its contents as a DataFrame.

        Args:
            path: Filesystem path to the data source.
            **kwargs: Reader-specific options (e.g. encoding, sheet name).

        Returns:
            A DataFrame with the file contents.

        Raises:
            FileNotFoundError: When *path* does not exist.
            ValueError: When the file cannot be parsed.
        """
        ...

    @abstractmethod
    def supports(self, ext: str) -> bool:
        """Return ``True`` if this reader can handle the given file extension.

        Args:
            ext: File extension including the dot, e.g. ``".csv"``.
        """
        ...


# ---------------------------------------------------------------------------
# Factory — detect reader by file extension
# ---------------------------------------------------------------------------

# Lazy-import readers here to avoid circular dependencies at module load.
# The registry is populated on first call to ``detect_reader()``.
_READERS: list[DataReader] | None = None


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _register_ocr_reader() -> None:
    """Lazy-register OcrReader if available (requires easyocr + pillow)."""
    try:
        from matchaudit.readers.ocr import OcrReader  # noqa: F401

        # Register in the existing reader list
        _READERS.append(OcrReader())
    except ImportError:
        pass


def _ensure_readers() -> list[DataReader]:
    """Lazy-initialise the reader registry."""
    global _READERS
    if _READERS is None:
        from matchaudit.readers.csv import CsvReader
        from matchaudit.readers.excel import ExcelReader

        _READERS = [CsvReader(), ExcelReader()]
        _register_ocr_reader()
    return _READERS


def detect_reader(path: Path) -> DataReader:
    """Select the appropriate reader for *path* based on its file extension.

    Args:
        path: Target file path.

    Returns:
        A ``DataReader`` instance that supports the file extension.

    Raises:
        ValueError: When no reader can handle the file extension.
    """
    ext = path.suffix.lower()
    for reader in _ensure_readers():
        if reader.supports(ext):
            return reader
    if ext in IMAGE_EXTENSIONS:
        raise ValueError(
            f"No reader found for {path!r} (extension {ext!r}). "
            "Image files require easyocr. "
            "Install with: pip install matchaudit[ocr]"
        )
    raise ValueError(
        f"No reader found for {path!r} (extension {ext!r}). "
        "Supported: .csv, .xlsx, .xls"
    )


__all__ = [
    "DataReader",
    "detect_reader",
]
