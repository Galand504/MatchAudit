"""Domain models for MatchAudit — pure dataclasses with no I/O dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pandas import DataFrame


@dataclass
class ControlPoint:
    """A named window into a source dataset that must be verified.

    Attributes:
        name: Human-readable label (e.g. "Bloque inicial").
        source: The full source dataset.
        label_column: Column used for ordering / slicing (e.g. "id").
        start_label: First record label to extract (inclusive).
        end_label: Last record label to extract (inclusive).
        description: Optional human-readable context.
    """

    name: str
    source: DataFrame
    label_column: str
    start_label: Any
    end_label: Any
    description: str = ""


@dataclass
class RowDiff:
    """A single cell-level difference between expected and captured data.

    Attributes:
        index: Row position in the source.
        key: Label value identifying the row (e.g. id=42).
        column: Which column differs; ``None`` when the whole row is missing.
        expected: Value in the expected data.
        actual: Value in the captured data.
    """

    index: int
    key: Any
    column: str | None
    expected: Any
    actual: Any


@dataclass
class RowShift:
    """A record present in both datasets but at a different position.

    Attributes:
        expected_position: Row index in the expected dataset.
        actual_position: Row index in the captured dataset.
        key: Label value identifying the shifted row.
        surrounding_rows: Tuple of (previous_key, next_key) for context.
    """

    expected_position: int
    actual_position: int
    key: Any
    surrounding_rows: tuple[Any, Any]


@dataclass
class ComparisonStats:
    """Aggregated statistics from a comparison run.

    Attributes:
        total_expected: Number of rows in the expected dataset.
        total_captured: Number of rows in the captured dataset.
        match_rate: Fraction of matched rows over max(total_expected, total_captured).
        has_misalignment: ``True`` when any mismatch, missing, extra, or shift exists.
        severity: Overall severity — ``"ok"``, ``"warning"``, or ``"critical"``.
    """

    total_expected: int
    total_captured: int
    match_rate: float
    has_misalignment: bool
    severity: Literal["ok", "warning", "critical"]


@dataclass
class ComparisonResult:
    """The complete output of comparing two datasets.

    Attributes:
        status: Overall status — ``"match"``, ``"mismatch"``, or ``"error"``.
        matched_rows: Count of identical rows.
        mismatched_rows: List of cell-level differences for rows present in both.
        missing_rows: Rows present in expected but absent from captured.
        extra_rows: Rows present in captured but absent from expected.
        shifted_rows: Rows present in both but at different positions.
        stats: Aggregated comparison statistics.
    """

    status: Literal["match", "mismatch", "error"]
    matched_rows: int
    mismatched_rows: list[RowDiff] = field(default_factory=list)
    missing_rows: list[RowDiff] = field(default_factory=list)
    extra_rows: list[RowDiff] = field(default_factory=list)
    shifted_rows: list[RowShift] = field(default_factory=list)
    stats: ComparisonStats | None = None
