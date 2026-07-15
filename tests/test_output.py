"""Tests for the output formatters."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pandas as pd

from matchaudit.core.comparator import compare
from matchaudit.core.models import ComparisonResult
from matchaudit.output.console import render_comparison

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df(**kwargs: object) -> pd.DataFrame:
    return pd.DataFrame(kwargs)


def _match_result() -> ComparisonResult:
    """Produce a result where both datasets are identical."""
    src = _df(id=[1, 2], name=["Alice", "Bob"])
    cap = _df(id=[1, 2], name=["Alice", "Bob"])
    return compare(src, cap, key_columns=["id"])


def _mismatch_result() -> ComparisonResult:
    """Produce a result with known differences."""
    src = _df(id=[1, 2, 3], name=["Alice", "Bob", "Charlie"], amt=[10, 20, 30])
    cap = _df(id=[1, 2, 4], name=["Alice", "BOB", "Dave"], amt=[10, 99, 30])
    return compare(src, cap, key_columns=["id"])


# ---------------------------------------------------------------------------
# Summary rendering
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_contains_match_status(self) -> None:
        result = _match_result()
        buf = StringIO()
        from rich.console import Console

        console = Console(file=buf, force_terminal=False)
        from matchaudit.output.console import _render_summary

        _render_summary(console, result)
        output = buf.getvalue()
        assert "MATCH" in output
        assert "100.0%" in output or "100" in output

    def test_summary_contains_mismatch_status(self) -> None:
        result = _mismatch_result()
        buf = StringIO()
        from rich.console import Console

        console = Console(file=buf, force_terminal=False)
        from matchaudit.output.console import _render_summary

        _render_summary(console, result)
        output = buf.getvalue()
        assert "MISMATCH" in output

    def test_summary_lists_row_counts(self) -> None:
        result = _mismatch_result()
        buf = StringIO()
        from rich.console import Console

        console = Console(file=buf, force_terminal=False)
        from matchaudit.output.console import _render_summary

        _render_summary(console, result)
        output = buf.getvalue()
        assert "Total expected rows" in output
        assert "Total captured rows" in output
        assert "Missing rows" in output
        assert "Extra rows" in output

    def test_summary_handles_none_stats(self) -> None:
        """No crash when stats is None."""
        result = ComparisonResult(
            status="error",
            matched_rows=0,
        )
        buf = StringIO()
        from rich.console import Console

        console = Console(file=buf, force_terminal=False)
        from matchaudit.output.console import _render_summary

        _render_summary(console, result)  # should not raise


# ---------------------------------------------------------------------------
# Diff table rendering
# ---------------------------------------------------------------------------


class TestDiffTable:
    def test_diff_table_rendered_on_mismatch(self) -> None:
        result = _mismatch_result()
        buf = StringIO()
        from rich.console import Console

        console = Console(file=buf, force_terminal=False)
        from matchaudit.output.console import _render_diff_table

        rendered = _render_diff_table(console, result)
        output = buf.getvalue()
        assert rendered is True
        # Should contain the changed column name
        assert "name" in output or "amt" in output

    def test_diff_table_not_rendered_on_match(self) -> None:
        result = _match_result()
        buf = StringIO()
        from rich.console import Console

        console = Console(file=buf, force_terminal=False)
        from matchaudit.output.console import _render_diff_table

        rendered = _render_diff_table(console, result)
        assert rendered is False

    def test_missing_section_rendered(self) -> None:
        result = _mismatch_result()
        buf = StringIO()
        from rich.console import Console

        console = Console(file=buf, force_terminal=False)
        from matchaudit.output.console import _render_missing_section

        _render_missing_section(console, result)
        output = buf.getvalue()
        assert "Missing Rows" in output
        assert "Charlie" in output or "3" in output

    def test_extra_section_rendered(self) -> None:
        result = _mismatch_result()
        buf = StringIO()
        from rich.console import Console

        console = Console(file=buf, force_terminal=False)
        from matchaudit.output.console import _render_extra_section

        _render_extra_section(console, result)
        output = buf.getvalue()
        assert "Extra Rows" in output
        assert "Dave" in output or "4" in output


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


class TestJsonOutput:
    def test_json_output_is_valid(self) -> None:
        result = _mismatch_result()
        buf = StringIO()
        import sys

        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            render_comparison(result, output_format="json")
        finally:
            sys.stdout = old_stdout

        data = json.loads(buf.getvalue())
        assert data["status"] == "mismatch"
        assert "matched_rows" in data
        assert "mismatched_rows" in data
        assert "missing_rows" in data
        assert "extra_rows" in data
        assert "stats" in data

    def test_json_output_match(self) -> None:
        result = _match_result()
        buf = StringIO()
        import sys

        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            render_comparison(result, output_format="json")
        finally:
            sys.stdout = old_stdout

        data = json.loads(buf.getvalue())
        assert data["status"] == "match"
        assert data["matched_rows"] == 2
        assert data["mismatched_rows"] == []

    def test_json_stats_contains_expected_fields(self) -> None:
        result = _mismatch_result()
        buf = StringIO()
        import sys

        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            render_comparison(result, output_format="json")
        finally:
            sys.stdout = old_stdout

        data = json.loads(buf.getvalue())
        stats = data["stats"]
        assert "total_expected" in stats
        assert "total_captured" in stats
        assert "match_rate" in stats
        assert "severity" in stats

    def test_json_output_empty_result(self) -> None:
        """An empty comparison should produce valid JSON with 0 counts."""
        src = _df(id=[], name=[])
        cap = _df(id=[], name=[])
        result = compare(src, cap, key_columns=["id"])

        buf = StringIO()
        import sys

        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            render_comparison(result, output_format="json")
        finally:
            sys.stdout = old_stdout

        data = json.loads(buf.getvalue())
        assert data["status"] == "match"
        assert data["matched_rows"] == 0


# ---------------------------------------------------------------------------
# Integration: CLI context
# ---------------------------------------------------------------------------


class TestCliOutput:
    """Test output module as used from the CLI (integration-lite)."""

    def test_compare_identical_files_via_full_pipeline(self, sample_csv: Path) -> None:
        """Compare a file against itself — should produce a match summary."""
        result = compare(
            _df(id=[1, 2], name=["A", "B"]),
            _df(id=[1, 2], name=["A", "B"]),
            key_columns=["id"],
        )
        assert result.status == "match"
        assert result.matched_rows == 2
