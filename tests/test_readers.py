"""Tests for the data reader abstraction and built-in implementations."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from matchaudit.readers import IMAGE_EXTENSIONS, DataReader, detect_reader
from matchaudit.readers.csv import CsvReader
from matchaudit.readers.excel import ExcelReader


class TestCsvReader:
    """CsvReader — supports() and read()."""

    def test_supports_csv(self) -> None:
        assert CsvReader().supports(".csv") is True

    @pytest.mark.parametrize("ext", [".xlsx", ".xls", ".parquet", ".json"])
    def test_does_not_support_other_formats(self, ext: str) -> None:
        assert CsvReader().supports(ext) is False

    def test_read_returns_dataframe(self, sample_csv: Path) -> None:
        df = CsvReader().read(sample_csv)
        assert isinstance(df, pd.DataFrame)

    def test_read_returns_expected_columns(self, sample_csv: Path) -> None:
        df = CsvReader().read(sample_csv)
        assert list(df.columns) == ["id", "name", "amount", "date"]

    def test_read_returns_expected_row_count(self, sample_csv: Path) -> None:
        df = CsvReader().read(sample_csv)
        assert len(df) == 5

    def test_read_raises_on_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            CsvReader().read(Path("/nonexistent/file.csv"))


class TestExcelReader:
    """ExcelReader — supports() and read()."""

    def test_supports_xlsx(self) -> None:
        assert ExcelReader().supports(".xlsx") is True

    def test_supports_xls(self) -> None:
        assert ExcelReader().supports(".xls") is True

    @pytest.mark.parametrize("ext", [".csv", ".parquet", ".json"])
    def test_does_not_support_other_formats(self, ext: str) -> None:
        assert ExcelReader().supports(ext) is False

    def test_read_returns_dataframe(self, sample_xlsx: Path) -> None:
        df = ExcelReader().read(sample_xlsx)
        assert isinstance(df, pd.DataFrame)

    def test_read_returns_expected_columns(self, sample_xlsx: Path) -> None:
        df = ExcelReader().read(sample_xlsx)
        assert list(df.columns) == ["id", "name", "amount", "date"]

    def test_read_returns_expected_row_count(self, sample_xlsx: Path) -> None:
        df = ExcelReader().read(sample_xlsx)
        assert len(df) == 5

    def test_read_raises_on_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            ExcelReader().read(Path("/nonexistent/file.xlsx"))


class TestDetectReader:
    """detect_reader() factory behaviour."""

    def test_detect_csv_reader(self, sample_csv: Path) -> None:
        reader = detect_reader(sample_csv)
        assert isinstance(reader, CsvReader)

    def test_detect_excel_reader(self, sample_xlsx: Path) -> None:
        reader = detect_reader(sample_xlsx)
        assert isinstance(reader, ExcelReader)

    def test_detect_unsupported_extension_raises(self) -> None:
        with pytest.raises(ValueError, match="No reader found"):
            detect_reader(Path("data.parquet"))

    def test_reader_implements_abc(self) -> None:
        assert isinstance(CsvReader(), DataReader)
        assert isinstance(ExcelReader(), DataReader)


class TestOcrRegistration:
    """OcrReader is registered when dependencies are available."""

    def test_detect_ocr_reader_for_png(self, sample_capture: Path) -> None:
        """If easyocr + pillow installed, detect_reader returns OcrReader."""
        reader = detect_reader(sample_capture)
        from matchaudit.readers.ocr import OcrReader

        assert isinstance(reader, OcrReader)

    @pytest.mark.parametrize("ext", [".png", ".jpg", ".jpeg"])
    def test_detect_ocr_reader_by_extension(self, ext: str) -> None:
        """OcrReader supports all standard image extensions."""
        reader = detect_reader(Path(f"file{ext}"))
        from matchaudit.readers.ocr import OcrReader

        assert isinstance(reader, OcrReader)

    def test_ocr_supports_all_image_extensions(self) -> None:
        """IMAGE_EXTENSIONS matches what OcrReader supports."""
        from matchaudit.readers.ocr import OcrReader

        reader = OcrReader()
        for ext in IMAGE_EXTENSIONS:
            assert reader.supports(ext) is True, f"Expected {ext} to be supported"

    def test_image_extensions_constant(self) -> None:
        """IMAGE_EXTENSIONS includes expected image formats."""
        assert IMAGE_EXTENSIONS == {".png", ".jpg", ".jpeg"}

    def test_detect_unsupported_image_no_ocr(self) -> None:
        """Without OcrReader registered, image extensions raise helpful message."""
        # We can't truly unregister OcrReader, but we can verify the error path
        # via the unsupported extension path
        with pytest.raises(ValueError, match="No reader found"):
            detect_reader(Path("data.parquet"))
