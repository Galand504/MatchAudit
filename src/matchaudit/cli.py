"""MatchAudit CLI — root command and subcommands."""

from __future__ import annotations

from pathlib import Path

import click

from matchaudit.core.comparator import compare as run_comparison
from matchaudit.core.control_point import extract
from matchaudit.output.console import render_comparison
from matchaudit.readers import detect_reader

# Common key-column candidates, in priority order
_KEY_COLUMN_CANDIDATES = [
    "id_pais",
    "id_revista",
    "id",
    "codigo",
    "nombre",
    "name",
    "code",
    "email",
    "username",
    "usuario",
    "slug",
    "reference",
    "referencia",
    "transaction_id",
    "documento",
    "numero",
    "nro",
]

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _auto_detect_key_columns(df_a, df_b) -> list[str] | None:
    """Find the first known key column present in both DataFrames."""
    common = set(df_a.columns) & set(df_b.columns)
    for candidate in _KEY_COLUMN_CANDIDATES:
        if candidate in common:
            return [candidate]
    # Fallback: first common column that looks like a key (unique values)
    for col in common:
        if df_a[col].nunique() == len(df_a) or df_b[col].nunique() == len(df_b):
            return [col]
    return None


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_EXTENSIONS


@click.group()
@click.version_option()
def main() -> None:
    """MatchAudit: data validation and reconciliation for audit teams."""


@main.command()
@click.option(
    "--source",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to the source data file (.csv / .xlsx / .png).",
)
@click.option(
    "--captured",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to the captured data file (.csv / .xlsx / .png).",
)
@click.option(
    "--key-columns",
    default=None,
    help="Comma-separated key column(s). Auto-detected when omitted.",
)
@click.option(
    "--label-column",
    default=None,
    help="Column for ordering/range slicing (optional).",
)
@click.option(
    "--start",
    default=None,
    type=str,
    help="Start label for range slicing, inclusive (optional).",
)
@click.option(
    "--end",
    default=None,
    type=str,
    help="End label for range slicing, inclusive (optional).",
)
@click.option(
    "--output",
    default=None,
    type=click.Choice(["json"]),
    help="Output format (default: Rich console).",
)
@click.option(
    "--ocr-language",
    default="es,en",
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
@click.option(
    "--ocr-upscale",
    is_flag=True,
    default=False,
    help="Upscale image before OCR (slower, better small-text detection).",
)
def compare(
    source: Path,
    captured: Path,
    key_columns: str | None,
    label_column: str | None,
    start: str | None,
    end: str | None,
    output: str | None,
    ocr_language: str,
    ocr_conf_threshold: float,
    ocr_upscale: bool,
) -> None:
    """Compare two datasets and report differences.

    Auto-detects OCR when a file is a PNG/JPEG image.  Key columns are
    auto-detected when omitted — just pass ``--source`` and ``--captured``.
    """
    try:
        # -- Auto-detect OCR -------------------------------------------------
        needs_ocr = _is_image(source) or _is_image(captured)
        if needs_ocr:
            try:
                import easyocr  # noqa: F401
            except ImportError:
                raise click.ClickException(
                    "EasyOCR is required for image files. "
                    "Install with: pip install matchaudit[ocr]"
                )

        # -- Read both files -------------------------------------------------
        source_reader = detect_reader(source)
        captured_reader = detect_reader(captured)

        if needs_ocr:
            from matchaudit.readers.ocr import OcrReader

            ocr_kwargs: dict[str, object] = {
                "language": [lang.strip() for lang in ocr_language.split(",")],
                "conf_threshold": ocr_conf_threshold,
                "ocr_upscale": ocr_upscale,
            }

            def _read_with_ocr(reader, path: Path):
                if isinstance(reader, OcrReader):
                    return reader.read(path, **ocr_kwargs)
                return reader.read(path)

            source_df = _read_with_ocr(source_reader, source)
            captured_df = _read_with_ocr(captured_reader, captured)
        else:
            source_df = source_reader.read(source)
            captured_df = captured_reader.read(captured)

        # -- Auto-detect key columns -----------------------------------------
        keys: list[str]
        if key_columns:
            keys = [k.strip() for k in key_columns.split(",")]
        else:
            detected = _auto_detect_key_columns(source_df, captured_df)
            if detected:
                keys = detected
                click.echo(f"ℹ️  Key column auto-detectada: {detected[0]}")
            else:
                raise click.ClickException(
                    "Could not auto-detect key columns. "
                    "Use --key-columns to specify them."
                )

        # -- Optional range slicing ------------------------------------------
        if label_column is not None and start is not None and end is not None:
            source_df = extract(source_df, label_column, start, end)
            captured_df = extract(captured_df, label_column, start, end)

        # -- Run comparison --------------------------------------------------
        result = run_comparison(source_df, captured_df, keys)
        render_comparison(result, output_format=output)

    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))


@main.command()
def validate() -> None:
    """Validate a control point against source data."""
    click.echo("validate: not yet implemented")


if __name__ == "__main__":
    main()
