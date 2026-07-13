"""DataFrame comparison engine — merge, classify rows, and produce cell-level diffs."""

from __future__ import annotations

from typing import Any

import pandas as pd

from matchaudit.core.models import (
    ComparisonResult,
    ComparisonStats,
    RowDiff,
    RowShift,
)


def compare(
    source_df: pd.DataFrame,
    captured_df: pd.DataFrame,
    key_columns: list[str],
) -> ComparisonResult:
    """Compare two DataFrames row by row using *key_columns* as row identifiers.

    Classification (via ``pd.merge(how="outer", indicator=True)``):
        - **matched**: rows present in both DataFrames (``both``).
        - **missing**: rows in *source_df* but absent from
          *captured_df* (``left_only``).
        - **extra**: rows in *captured_df* but absent from
          *source_df* (``right_only``).

    For matched rows, a column-by-column diff is performed on every column
    that is *not* in *key_columns*.

    Args:
        source_df: The expected / reference DataFrame.
        captured_df: The actual / captured DataFrame.
        key_columns: Column names that uniquely identify a row.

    Returns:
        A ``ComparisonResult`` containing row classifications, cell-level diffs
        for matched-but-changed rows, shift candidates, and aggregate stats.

    Raises:
        ValueError: If *key_columns* are not present in either DataFrame.
    """
    _validate_input(source_df, captured_df, key_columns)

    # ------------------------------------------------------------------
    # Row classification — outer merge with indicator
    # ------------------------------------------------------------------
    merged = pd.merge(
        source_df,
        captured_df,
        on=key_columns,
        how="outer",
        indicator=True,
        suffixes=("_expected", "_actual"),
    )

    matched_mask = merged["_merge"] == "both"
    missing_mask = merged["_merge"] == "left_only"
    extra_mask = merged["_merge"] == "right_only"

    matched_count = int(matched_mask.sum())

    # ------------------------------------------------------------------
    # Column-by-column diff on matched rows (exclude key columns)
    # ------------------------------------------------------------------
    value_columns = [
        col for col in source_df.columns if col not in key_columns
    ]

    mismatched_rows: list[RowDiff] = []
    matched_subset = merged[matched_mask]

    for _, row in matched_subset.iterrows():
        for col in value_columns:
            # Resolve suffixed column names (merge renames colliding cols)
            exp_sfx = f"{col}_expected"
            expected_col = (
                exp_sfx if exp_sfx in matched_subset.columns else col
            )
            act_sfx = f"{col}_actual"
            actual_col = (
                act_sfx if act_sfx in matched_subset.columns else col
            )

            expected_val = row[expected_col]
            actual_val = row[actual_col]

            if _values_differ(expected_val, actual_val):
                key_val = _make_key(row, key_columns)
                idx = (
                    int(row.name)
                    if isinstance(row.name, (int, float))
                    else 0
                )
                mismatched_rows.append(
                    RowDiff(
                        index=idx,
                        key=key_val,
                        column=col,
                        expected=_serialize(expected_val),
                        actual=_serialize(actual_val),
                    )
                )

    # ------------------------------------------------------------------
    # Missing rows (in source but not in captured)
    # ------------------------------------------------------------------
    missing_rows: list[RowDiff] = []
    missing_subset = merged[missing_mask]
    for _, row in missing_subset.iterrows():
        idx = (
            int(row.name)
            if isinstance(row.name, (int, float))
            else 0
        )
        missing_rows.append(
            RowDiff(
                index=idx,
                key=_make_key(row, key_columns),
                column=None,
                expected="(present in source)",
                actual="(missing in captured)",
            )
        )

    # ------------------------------------------------------------------
    # Extra rows (in captured but not in source)
    # ------------------------------------------------------------------
    extra_rows: list[RowDiff] = []
    extra_subset = merged[extra_mask]
    for _, row in extra_subset.iterrows():
        idx = (
            int(row.name)
            if isinstance(row.name, (int, float))
            else 0
        )
        extra_rows.append(
            RowDiff(
                index=idx,
                key=_make_key(row, key_columns),
                column=None,
                expected="(missing in source)",
                actual="(extra in captured)",
            )
        )

    # ------------------------------------------------------------------
    # Shift detection
    # ------------------------------------------------------------------
    shifted_rows = _detect_shifts(
        source_df, captured_df, key_columns, missing_subset, extra_subset
    )

    # ------------------------------------------------------------------
    # Aggregate statistics
    # ------------------------------------------------------------------
    total_expected = len(source_df)
    total_captured = len(captured_df)
    max_total = max(total_expected, total_captured)
    match_rate = matched_count / max_total if max_total > 0 else 1.0

    has_misalignment = bool(
        mismatched_rows or missing_rows or extra_rows or shifted_rows
    )

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


# ── Internal helpers ──────────────────────────────────────────────────────


def _validate_input(
    source_df: pd.DataFrame,
    captured_df: pd.DataFrame,
    key_columns: list[str],
) -> None:
    """Validate pre-conditions before running a comparison."""
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
    """Extract the row identifier from *key_columns*.

    Returns a scalar for single-column keys, a tuple for compound keys.
    """
    if len(key_columns) == 1:
        return row[key_columns[0]]
    return tuple(row[k] for k in key_columns)


def _serialize(val: Any) -> Any:
    """Normalise a cell value for safe display / comparison output."""
    if pd.isna(val):
        return None
    return val


def _values_differ(a: Any, b: Any) -> bool:
    """Return ``True`` when two cell values are semantically different.

    Treats NaN/None as equal to NaN/None (pandas ``NaN != NaN`` would
    otherwise always return ``True``).
    """
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
    """Detect rows present in both DataFrames but at different positions.

    Heuristic: when the same number of missing and extra rows exist, sort
    both by key column(s) and pair them positionally.  This catches simple
    insertions / deletions that push subsequent rows by one position.

    Returns:
        A list of ``RowShift`` records; empty when no shifts are detected.
    """
    shifted: list[RowShift] = []

    if missing_df.empty or extra_df.empty:
        return shifted

    if len(missing_df) != len(extra_df):
        return shifted

    sort_cols = key_columns[:1]  # sort by the first key column
    missing_sorted = missing_df.sort_values(by=sort_cols).reset_index(drop=True)
    extra_sorted = extra_df.sort_values(by=sort_cols).reset_index(drop=True)

    for i in range(len(missing_sorted)):
        miss_row = missing_sorted.iloc[i]
        extra_row = extra_sorted.iloc[i]
        key_val = _make_key(miss_row, key_columns)

        exp_pos = (
            int(miss_row.name)
            if isinstance(miss_row.name, (int, float))
            else 0
        )
        act_pos = (
            int(extra_row.name)
            if isinstance(extra_row.name, (int, float))
            else 0
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
