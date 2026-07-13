"""Control point operations — slice extraction and key uniqueness validation."""

from __future__ import annotations

from typing import Any

import pandas as pd


def extract(
    df: pd.DataFrame,
    label_column: str,
    start_label: Any,
    end_label: Any,
) -> pd.DataFrame:
    """Extract a slice of *df* between *start_label* and *end_label* (inclusive).

    The returned DataFrame is sorted by *label_column*.

    Args:
        df: The source DataFrame.
        label_column: Column used for ordering and range filtering.
        start_label: First label value to include (inclusive).
        end_label: Last label value to include (inclusive).

    Returns:
        A DataFrame containing only rows where *label_column*
        falls in the range [*start_label*, *end_label*].

    Raises:
        ValueError: If *label_column* is not found in *df*.
    """
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
    """Check that the combination of *key_columns* is unique in *df*.

    Args:
        df: The DataFrame to check.
        key_columns: Column names that should form a unique key.
        label: Human-readable label for error messages (e.g. ``"source"``).

    Raises:
        ValueError: If any of *key_columns* are missing from *df* or if
            duplicate key combinations exist.
    """
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
