"""Excel reader — loads ``.xlsx`` files via pandas + openpyxl."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas import DataFrame

from matchaudit.readers import DataReader


class ExcelReader(DataReader):
    """Read Excel (.xlsx) files using ``pd.read_excel(engine='openpyxl')``.

    By default reads the first sheet. Pass ``sheet_name`` in kwargs
    to target a specific sheet by name or index.
    """

    def read(self, path: Path, **kwargs: object) -> DataFrame:
        """Read an Excel file and return a DataFrame.

        Args:
            path: Path to an ``.xlsx`` file.
            **kwargs: Passed through to ``pd.read_excel``
                (e.g. ``sheet_name``, ``dtype``, ``header``).

        Returns:
            DataFrame with the sheet contents.

        Raises:
            FileNotFoundError: When *path* does not exist.
            ValueError: When the file cannot be parsed as Excel.
        """
        if not path.exists():
            raise FileNotFoundError(f"Excel file not found: {path}")

        # pandas < 2.x accepts read_excel kwargs differently, but we
        # target >= 2.1 so we can pass kwargs directly.
        return pd.read_excel(path, engine="openpyxl", **kwargs)  # type: ignore[arg-type]

    def supports(self, ext: str) -> bool:
        """Return ``True`` for ``.xlsx`` and ``.xls`` extensions."""
        return ext in {".xlsx", ".xls"}
