"""CSV reader — loads ``.csv`` files via pandas with UTF-8 BOM handling."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas import DataFrame

from matchaudit.readers import DataReader


class CsvReader(DataReader):
    """Read CSV files using ``pd.read_csv()`` with sensible defaults.

    Default behaviour:
    - UTF-8 encoding with BOM handling (``utf-8-sig``).
    - Auto-detect header row.
    - Fallback to ``utf-8`` if ``utf-8-sig`` fails (no BOM is harmless).
    - Pass ``encoding`` in kwargs to override.
    """

    def read(self, path: Path, **kwargs: object) -> DataFrame:
        """Read a CSV file and return a DataFrame.

        Args:
            path: Path to a ``.csv`` file.
            **kwargs: Passed through to ``pd.read_csv``
                (e.g. ``sep``, ``dtype``, ``encoding``, ``na_values``).

        Returns:
            DataFrame with the file contents.

        Raises:
            FileNotFoundError: When *path* does not exist.
            ValueError: When the file cannot be parsed as CSV.
        """
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        # Use utf-8-sig by default — it transparently handles a UTF-8 BOM
        # and is a no-op when no BOM is present.
        encoding = kwargs.pop("encoding", "utf-8-sig")

        return pd.read_csv(path, encoding=encoding, **kwargs)  # type: ignore[arg-type]

    def supports(self, ext: str) -> bool:
        """Return ``True`` for ``.csv`` extension."""
        return ext == ".csv"
