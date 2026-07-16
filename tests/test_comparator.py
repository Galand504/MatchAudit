"""Tests for the comparison engine — ``compare()``."""

from __future__ import annotations

import pandas as pd
import pytest

from matchaudit.core.comparator import compare
from matchaudit.core.models import ComparisonResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df(**kwargs: object) -> pd.DataFrame:
    """Build a small DataFrame from column-oriented keyword arguments."""
    return pd.DataFrame(kwargs)


# ---------------------------------------------------------------------------
# Identical datasets
# ---------------------------------------------------------------------------


class TestIdentical:
    def test_identical_dataframes(self) -> None:
        src = _df(id=[1, 2], name=["Alice", "Bob"])
        cap = _df(id=[1, 2], name=["Alice", "Bob"])
        result = compare(src, cap, key_columns=["id"])
        assert result.status == "match"
        assert result.matched_rows == 2
        assert result.mismatched_rows == []
        assert result.missing_rows == []
        assert result.extra_rows == []

    def test_identical_single_row(self) -> None:
        src = _df(id=[42], val=["x"])
        cap = _df(id=[42], val=["x"])
        result = compare(src, cap, ["id"])
        assert result.status == "match"
        assert result.stats is not None
        assert result.stats.match_rate == 1.0


# ---------------------------------------------------------------------------
# Mismatched values
# ---------------------------------------------------------------------------


class TestMismatch:
    def test_cell_value_differs(self) -> None:
        src = _df(id=[1], name=["Alice"], amount=[100.0])
        cap = _df(id=[1], name=["Alice"], amount=[999.0])
        result = compare(src, cap, key_columns=["id"])
        assert result.status == "mismatch"
        assert len(result.mismatched_rows) == 1
        diff = result.mismatched_rows[0]
        assert diff.column == "amount"
        assert diff.expected == 100.0
        assert diff.actual == 999.0

    def test_multiple_mismatches_in_one_row(self) -> None:
        src = _df(id=[1], name=["Alice"], amount=[100.0])
        cap = _df(id=[1], name=["Bob"], amount=[200.0])
        result = compare(src, cap, key_columns=["id"])
        assert len(result.mismatched_rows) == 2
        columns = {d.column for d in result.mismatched_rows}
        assert columns == {"name", "amount"}

    def test_mismatch_shared_key(self) -> None:
        """Same key, but extra columns differ."""
        src = _df(id=[1, 2], name=["A", "B"], val=["x", "y"])
        cap = _df(id=[1, 2], name=["A", "C"], val=["x", "z"])
        result = compare(src, cap, ["id"])
        assert result.status == "mismatch"
        assert result.matched_rows == 2
        assert len(result.mismatched_rows) == 2  # B-name, B-val


# ---------------------------------------------------------------------------
# Missing and extra rows
# ---------------------------------------------------------------------------


class TestMissingRows:
    def test_row_missing_from_captured(self) -> None:
        src = _df(id=[1, 2, 3], name=["A", "B", "C"])
        cap = _df(id=[1, 2], name=["A", "B"])
        result = compare(src, cap, key_columns=["id"])
        assert result.status == "mismatch"
        assert len(result.missing_rows) == 1
        assert result.missing_rows[0].key == "3"
        assert result.stats is not None
        assert result.stats.severity == "critical"

    def test_multiple_missing_rows(self) -> None:
        src = _df(id=[1, 2, 3, 4], name=["A", "B", "C", "D"])
        cap = _df(id=[1], name=["A"])
        result = compare(src, cap, key_columns=["id"])
        assert len(result.missing_rows) == 3


class TestExtraRows:
    def test_row_extra_in_captured(self) -> None:
        src = _df(id=[1, 2], name=["A", "B"])
        cap = _df(id=[1, 2, 3], name=["A", "B", "C"])
        result = compare(src, cap, key_columns=["id"])
        assert result.status == "mismatch"
        assert len(result.extra_rows) == 1
        assert result.extra_rows[0].key == "3"

    def test_multiple_extra_rows(self) -> None:
        src = _df(id=[1], name=["A"])
        cap = _df(id=[1, 2, 3], name=["A", "B", "C"])
        result = compare(src, cap, key_columns=["id"])
        assert len(result.extra_rows) == 2


# ---------------------------------------------------------------------------
# Shift detection
# ---------------------------------------------------------------------------


class TestShiftedRows:
    def test_shift_with_insertion(self) -> None:
        """A row inserted in the middle — missing detected, no extra."""
        src = _df(id=[1, 2, 3], name=["A", "B", "C"])
        cap = _df(id=[1, 3], name=["A", "C"])
        result = compare(src, cap, key_columns=["id"])
        assert len(result.missing_rows) == 1


# ---------------------------------------------------------------------------
# Empty and edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_both_empty(self) -> None:
        src = _df(id=[], name=[])
        cap = _df(id=[], name=[])
        result = compare(src, cap, key_columns=["id"])
        assert result.status == "match"
        assert result.matched_rows == 0
        assert result.stats is not None
        assert result.stats.match_rate == 1.0

    def test_source_empty_captured_has_rows(self) -> None:
        src = _df(id=[], name=[])
        cap = _df(id=[1], name=["A"])
        result = compare(src, cap, key_columns=["id"])
        assert result.status == "mismatch"
        assert len(result.extra_rows) == 1

    def test_captured_empty_source_has_rows(self) -> None:
        src = _df(id=[1], name=["A"])
        cap = _df(id=[], name=[])
        result = compare(src, cap, key_columns=["id"])
        assert result.status == "mismatch"
        assert len(result.missing_rows) == 1

    def test_duplicate_keys_do_not_crash(self) -> None:
        """Duplicate keys cause a Cartesian merge explosion but the
        comparator handles it gracefully (precondition validation is
        expected to happen at the ``ControlPoint`` level)."""
        src = _df(id=[1, 1], name=["A", "B"])
        cap = _df(id=[1], name=["A"])
        result = compare(src, cap, key_columns=["id"])
        # Should still produce a result without raising
        assert result.status == "mismatch"
        assert result.matched_rows == 2  # cross-join = 2 both rows

    def test_missing_key_column_raises_value_error(self) -> None:
        src = _df(id=[1], name=["A"])
        cap = _df(id=[1], name=["A"])
        with pytest.raises(ValueError, match="not found"):
            compare(src, cap, key_columns=["nonexistent"])

    def test_empty_key_columns_raises_value_error(self) -> None:
        src = _df(id=[1], name=["A"])
        cap = _df(id=[1], name=["A"])
        with pytest.raises(ValueError, match="At least one key column"):
            compare(src, cap, key_columns=[])

    def test_multi_column_key(self) -> None:
        src = _df(id=[1, 1], type=["a", "b"], val=["x", "y"])
        cap = _df(id=[1, 1], type=["a", "b"], val=["x", "z"])
        result = compare(src, cap, key_columns=["id", "type"])
        assert result.matched_rows == 2
        assert len(result.mismatched_rows) == 1
        assert result.mismatched_rows[0].key == ("1", "b")

    def test_nan_values_match(self) -> None:
        """NaN in both DataFrames at the same position should NOT be
        reported as a mismatch."""
        src = _df(id=[1], val=[float("nan")])
        cap = _df(id=[1], val=[float("nan")])
        result = compare(src, cap, key_columns=["id"])
        assert result.status == "match"
        assert len(result.mismatched_rows) == 0

    def test_compare_returns_comparison_result(self) -> None:
        src = _df(id=[1], name=["A"])
        cap = _df(id=[1], name=["A"])
        result = compare(src, cap, key_columns=["id"])
        assert isinstance(result, ComparisonResult)
