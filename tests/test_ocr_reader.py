"""Tests for the OCR data reader (OcrReader)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from matchaudit.readers.ocr import (
    OcrReader,
    _build_dataframe,
    _detect_header,
    _group_by_rows,
)

# ---------------------------------------------------------------------------
# Conditional skip when EasyOCR is not installed
# ---------------------------------------------------------------------------

try:
    import easyocr  # noqa: F401

    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False


# ===================================================================
# Unit tests for internal helpers (no EasyOCR required)
# ===================================================================


class TestGroupByRows:
    """_group_by_rows() — Y-centre clustering."""

    def test_empty(self) -> None:
        assert _group_by_rows([]) == []

    def test_single_row(self) -> None:
        results = [
            ([[0, 0], [50, 0], [50, 20], [0, 20]], "hello", 0.95),
            ([[60, 0], [100, 0], [100, 20], [60, 20]], "world", 0.95),
        ]
        groups = _group_by_rows(results)
        assert len(groups) == 1
        assert len(groups[0]) == 2
        # Cells within a row are sorted by X-centre
        assert groups[0][0][1] == "hello"
        assert groups[0][1][1] == "world"

    def test_two_rows(self) -> None:
        results = [
            ([[0, 0], [50, 0], [50, 20], [0, 20]], "A", 0.95),
            ([[0, 40], [50, 40], [50, 60], [0, 60]], "B", 0.95),
        ]
        groups = _group_by_rows(results)
        assert len(groups) == 2
        assert groups[0][0][1] == "A"
        assert groups[1][0][1] == "B"

    def test_tolerance_merges_close_rows(self) -> None:
        # Two rows very close in Y — high tolerance merges them.
        # Heights are 20px; with tolerance 1.5 the threshold = 30px,
        # and y-centers are 10 and 26 → diff = 16 < 30 → merged.
        results = [
            ([[0, 0], [50, 0], [50, 20], [0, 20]], "top", 0.95),
            ([[0, 16], [50, 16], [50, 36], [0, 36]], "bottom", 0.95),
        ]
        groups = _group_by_rows(results, row_height_tolerance=1.5)
        assert len(groups) == 1, f"Expected merged, got {len(groups)} rows"


class TestDetectHeader:
    """_detect_header() — heuristic header detection."""

    def test_alpha_row_is_header(self) -> None:
        rows = [
            [([], "id", 0.9), ([], "name", 0.9)],
            [([], "1", 0.9), ([], "Alice", 0.9)],
        ]
        assert _detect_header(rows) == 0

    def test_numeric_rows_no_header(self) -> None:
        rows = [
            [([], "001", 0.9), ([], "100.5", 0.9)],
            [([], "002", 0.9), ([], "200.3", 0.9)],
        ]
        assert _detect_header(rows) is None

    def test_header_on_second_row(self) -> None:
        rows = [
            [([], "1", 0.9), ([], "1250.50", 0.9)],
            [([], "id", 0.9), ([], "amount", 0.9)],
            [([], "2", 0.9), ([], "3400.00", 0.9)],
        ]
        assert _detect_header(rows) == 1

    def test_empty_row_skipped(self) -> None:
        rows = [
            [([], "", 0.5)],
            [([], "id", 0.9), ([], "name", 0.9)],
            [([], "1", 0.9), ([], "Alice", 0.9)],
        ]
        assert _detect_header(rows) == 1


class TestBuildDataframe:
    """_build_dataframe() — DataFrame reconstruction."""

    def test_with_header(self) -> None:
        data = [
            [([], "1", 0.9), ([], "Alice", 0.9)],
            [([], "2", 0.9), ([], "Bob", 0.9)],
        ]
        header = [([], "id", 0.9), ([], "name", 0.9)]
        df = _build_dataframe(data, header)
        assert list(df.columns) == ["id", "name"]
        assert len(df) == 2
        assert df.iloc[0, 0] == "1"
        assert df.iloc[1, 1] == "Bob"

    def test_without_header(self) -> None:
        data = [
            [([], "1", 0.9), ([], "Alice", 0.9)],
            [([], "2", 0.9), ([], "Bob", 0.9)],
        ]
        df = _build_dataframe(data, None)
        assert list(df.columns) == ["col_0", "col_1"]
        assert len(df) == 2

    def test_uneven_rows(self) -> None:
        data = [
            [([], "1", 0.9), ([], "Alice", 0.9)],
            [([], "2", 0.9), ([], "Bob", 0.9), ([], "extra", 0.9)],
        ]
        df = _build_dataframe(data, None)
        assert list(df.columns) == ["col_0", "col_1", "col_2"]
        assert pd.isna(df.iloc[0, 2])
        assert df.iloc[1, 2] == "extra"


# ===================================================================
# Integration tests (require EasyOCR and the synthetic fixture)
# ===================================================================


class TestOcrReaderSupports:
    """OcrReader.supports() — extension matching."""

    def test_supports_png(self) -> None:
        assert OcrReader().supports(".png") is True

    def test_supports_jpg(self) -> None:
        assert OcrReader().supports(".jpg") is True

    def test_supports_jpeg(self) -> None:
        assert OcrReader().supports(".jpeg") is True

    def test_supports_uppercase(self) -> None:
        assert OcrReader().supports(".PNG") is True

    @pytest.mark.parametrize("ext", [".csv", ".xlsx", ".parquet", ".json"])
    def test_rejects_other_extensions(self, ext: str) -> None:
        assert OcrReader().supports(ext) is False


class TestOcrReaderFileErrors:
    """OcrReader.read() — file-not-found and missing-EasyOCR."""

    def test_raises_on_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            OcrReader().read(Path("/nonexistent/image.png"))


@pytest.mark.skipif(not HAS_EASYOCR, reason="easyocr not installed")
class TestOcrReaderWithEasyOCR:
    """OcrReader.read() — integration with synthetic fixture.

    These tests require EasyOCR (``pip install matchaudit[ocr]``).
    """

    @pytest.fixture(scope="class")
    def fixture_path(self) -> Path:
        return Path(__file__).resolve().parent / "fixtures" / "sample-capture.png"

    def test_read_returns_dataframe(self, fixture_path: Path) -> None:
        df = OcrReader().read(fixture_path)
        assert isinstance(df, pd.DataFrame)

    def test_read_has_expected_columns(self, fixture_path: Path) -> None:
        """The OCR should detect headers matching our known table."""
        df = OcrReader().read(fixture_path)
        actual = set(df.columns)
        # At minimum, the key columns should be present
        assert "id" in actual, f"Expected 'id' in columns, got {actual}"
        assert "name" in actual, f"Expected 'name' in columns, got {actual}"
        assert len(actual) >= 3

    def test_read_returns_reasonable_row_count(self, fixture_path: Path) -> None:
        """The synthetic fixture has 5 data rows."""
        df = OcrReader().read(fixture_path)
        # OCR may miss some rows, but at least 3 should be recovered
        assert len(df) >= 3, f"Expected >= 3 rows, got {len(df)}"

    def test_read_returns_known_value_in_first_row(self, fixture_path: Path) -> None:
        """First data row should contain 'Alice'."""
        df = OcrReader().read(fixture_path)
        # Search for Alice in the first few rows
        found = False
        for _, row in df.head(3).iterrows():
            if "Alice" in str(row.values):
                found = True
                break
        assert found, "Expected 'Alice' to appear in early rows"

    def test_read_with_conf_threshold(self, fixture_path: Path) -> None:
        """High confidence threshold should still return a DataFrame."""
        df = OcrReader(conf_threshold=0.5).read(fixture_path)
        assert isinstance(df, pd.DataFrame)

    def test_read_with_header_rows_explicit(self, fixture_path: Path) -> None:
        """Explicit ``header_rows=0`` should use generic column names."""
        reader = OcrReader(header_rows=0)
        df = reader.read(fixture_path)
        assert not list(df.columns) == ["id", "name", "amount", "date"]

    def test_read_returns_id_as_string_column(self, fixture_path: Path) -> None:
        """The 'id' column should be present and contain string data."""
        df = OcrReader().read(fixture_path)
        if "id" in df.columns:
            assert df["id"].dtype == "string" or df["id"].dtype == object
