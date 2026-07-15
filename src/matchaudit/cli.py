"""MatchAudit CLI — root command and subcommands."""

from __future__ import annotations

from pathlib import Path

import click

from matchaudit.core.comparator import compare as run_comparison
from matchaudit.core.control_point import extract
from matchaudit.output.console import render_comparison
from matchaudit.readers import detect_reader


@click.group()
@click.version_option()
def main() -> None:
    """MatchAudit: data validation and reconciliation for audit teams."""


@main.command()
@click.option(
    "--source",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to the source data file (.csv / .xlsx).",
)
@click.option(
    "--captured",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to the captured data file (.csv / .xlsx).",
)
@click.option(
    "--key-columns",
    required=True,
    help="Comma-separated list of key column names (e.g. ``id,transaction``).",
)
@click.option(
    "--label-column",
    default=None,
    help="Column used for ordering and range slicing (optional).",
)
@click.option(
    "--start",
    default=None,
    type=str,
    help="Start label value for range slicing, inclusive (optional).",
)
@click.option(
    "--end",
    default=None,
    type=str,
    help="End label value for range slicing, inclusive (optional).",
)
@click.option(
    "--output",
    default=None,
    type=click.Choice(["json"]),
    help="Output format (default: Rich console).",
)
@click.option(
    "--ocr",
    is_flag=True,
    default=False,
    help="Force OCR processing for image files (requires easyocr).",
)
@click.option(
    "--ocr-language",
    default="en",
    show_default=True,
    help="OCR language(s), comma-separated.",
)
@click.option(
    "--ocr-conf-threshold",
    default=0.0,
    type=float,
    show_default=True,
    help="OCR confidence threshold (0.0-1.0).",
)
def compare(
    source: Path,
    captured: Path,
    key_columns: str,
    label_column: str | None,
    start: str | None,
    end: str | None,
    output: str | None,
    ocr: bool,
    ocr_language: str,
    ocr_conf_threshold: float,
) -> None:
    """Compare two datasets and report differences.

    Reads *source* and *captured* files (auto-detected by extension),
    optionally slices by label range, runs a row-by-row comparison, and
    displays the result.
    """
    try:
        # 1. Detect readers and load DataFrames
        if ocr:
            try:
                import easyocr  # noqa: F401
            except ImportError:
                raise click.ClickException(
                    "EasyOCR is not installed. "
                    "Install with: pip install matchaudit[ocr]"
                )
            from matchaudit.readers.ocr import OcrReader

            lang_list = [lang.strip() for lang in ocr_language.split(",")]
            source_reader = OcrReader(
                language=lang_list, conf_threshold=ocr_conf_threshold
            )
            captured_reader = OcrReader(
                language=lang_list, conf_threshold=ocr_conf_threshold
            )
        else:
            source_reader = detect_reader(source)
            captured_reader = detect_reader(captured)

        source_df = source_reader.read(source)
        captured_df = captured_reader.read(captured)

        # 2. Parse key columns
        keys = [k.strip() for k in key_columns.split(",")]

        # 3. Apply optional range slicing when all three are present
        if label_column is not None and start is not None and end is not None:
            source_df = extract(source_df, label_column, start, end)
            captured_df = extract(captured_df, label_column, start, end)

        # 4. Run the comparison engine
        result = run_comparison(source_df, captured_df, keys)

        # 5. Render output
        render_comparison(result, output_format=output)

    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))


@main.command()
def validate() -> None:
    """Validate a control point against source data."""
    click.echo("validate: not yet implemented")


if __name__ == "__main__":
    main()
