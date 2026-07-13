"""Rich console output for comparison results.

Provides ``render_comparison()`` which detects TTY, renders a summary
Panel and a diff Table via Rich, or outputs structured JSON when
``output_format="json"``.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from matchaudit.core.models import (
    ComparisonResult,
    ComparisonStats,
    RowDiff,
    RowShift,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_comparison(
    result: ComparisonResult,
    output_format: str | None = None,
) -> None:
    """Render a ``ComparisonResult`` to stdout.

    Args:
        result: The comparison result to display.
        output_format:
            If ``"json"``, writes a JSON payload to stdout and returns.
            If ``None``, uses Rich with automatic TTY detection.
    """
    if output_format == "json":
        _render_json(result)
        return

    _render_rich(result)


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def _render_json(result: ComparisonResult) -> None:
    """Write the comparison result as a JSON object to stdout."""
    data = _result_to_dict(result)
    json.dump(data, sys.stdout, indent=2, default=str, ensure_ascii=False)
    sys.stdout.write("\n")


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


def _safe_str(val: Any) -> str | None:
    """Return a string representation or ``None`` for null-like values."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return str(val)
    return str(val)


# ---------------------------------------------------------------------------
# Rich console output
# ---------------------------------------------------------------------------


def _render_rich(result: ComparisonResult) -> None:
    """Render via Rich, respecting TTY detection."""
    # Lazy-import Rich so the module can be imported without it installed.
    from rich.console import Console

    console = Console()

    _render_summary(console, result)

    if result.status == "mismatch":
        has_content = _render_diff_table(console, result)
        _render_missing_section(console, result)
        _render_extra_section(console, result)
        if not has_content and not result.missing_rows and not result.extra_rows:
            console.print("[dim]No cell-level differences to display.[/dim]")


def _render_summary(console: Any, result: ComparisonResult) -> None:
    """Render a summary ``Panel`` with match statistics."""
    stats = result.stats
    if stats is None:
        return

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

    from rich.panel import Panel

    panel = Panel("\n".join(lines), title=title, border_style=border_style)
    console.print(panel)


def _render_diff_table(console: Any, result: ComparisonResult) -> bool:
    """Render a ``Table`` of cell-level differences.

    Returns:
        ``True`` if at least one row was rendered.
    """
    diffs = list(result.mismatched_rows)
    if not diffs:
        return False

    from rich.table import Table

    table = Table(title="Cell-Level Differences")
    table.add_column("Index", style="dim")
    table.add_column("Key")
    table.add_column("Column")
    table.add_column("Expected", style="cyan")
    table.add_column("Actual", style="red")

    for d in diffs:
        table.add_row(
            str(d.index),
            _safe_str(d.key) or "",
            d.column or "\u2014",
            _safe_str(d.expected) or "(empty)",
            _safe_str(d.actual) or "(empty)",
        )

    console.print(table)
    return True


def _render_missing_section(console: Any, result: ComparisonResult) -> None:
    """Render a table of rows present in source but missing from captured."""
    if not result.missing_rows:
        return

    from rich.table import Table

    table = Table(title="Missing Rows (in source, not in captured)")
    table.add_column("Index", style="dim")
    table.add_column("Key")
    for d in result.missing_rows:
        table.add_row(str(d.index), _safe_str(d.key) or "")
    console.print(table)


def _render_extra_section(console: Any, result: ComparisonResult) -> None:
    """Render a table of rows present in captured but not in source."""
    if not result.extra_rows:
        return

    from rich.table import Table

    table = Table(title="Extra Rows (in captured, not in source)")
    table.add_column("Index", style="dim")
    table.add_column("Key")
    for d in result.extra_rows:
        table.add_row(str(d.index), _safe_str(d.key) or "")
    console.print(table)
