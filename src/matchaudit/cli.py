"""MatchAudit CLI — root command and subcommands."""

from __future__ import annotations

from pathlib import Path

import click

from matchaudit.core.comparator import compare as run_comparison
from matchaudit.core.control_point import extract
from matchaudit.core.models import ComparisonResult
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
@click.option(
    "--source-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory with source files (.csv / .xlsx).",
)
@click.option(
    "--captured-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory with captured files (.png / .jpg / .jpeg).",
)
@click.option(
    "--key-columns",
    default=None,
    help="Comma-separated key column(s). Auto-detected when omitted.",
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
    help="Upscale images before OCR (slower, better small-text detection).",
)
def batch_compare(
    source_dir: Path,
    captured_dir: Path,
    key_columns: str | None,
    ocr_language: str,
    ocr_conf_threshold: float,
    ocr_upscale: bool,
) -> None:
    """Compare all source files against corresponding captures, matched by filename.

    For each file in SOURCE_DIR, looks for a matching file (same stem) in
    CAPTURED_DIR.  Source files: .csv, .xlsx.  Captured files: .png, .jpg, .jpeg.

    Prints a summary table with per-pair results and detailed breakdowns for
    every comparison that has mismatches.
    """
    from rich.console import Console

    console = Console()

    # -- Scan & match ---------------------------------------------------------
    pairs, unmatched_src, unmatched_cap = _find_batch_pairs(
        source_dir, captured_dir
    )

    if not pairs:
        msg = "No matching file pairs found between directories."
        if unmatched_src:
            msg += f"\n  Unmatched source files: {', '.join(sorted(unmatched_src))}"
        if unmatched_cap:
            msg += f"\n  Unmatched captured files: {', '.join(sorted(unmatched_cap))}"
        raise click.ClickException(msg)

    if unmatched_src:
        _warn_unmatched(console, "source", sorted(unmatched_src), source_dir)
    if unmatched_cap:
        _warn_unmatched(console, "captured", sorted(unmatched_cap), captured_dir)

    # -- Pre-load OcrReader once for all images -------------------------------
    ocr_reader = None
    if any(_is_image(cap) for _, _, cap in pairs):
        try:
            import easyocr  # noqa: F401
            from matchaudit.readers.ocr import OcrReader

            ocr_reader = OcrReader()
        except ImportError:
            raise click.ClickException(
                "EasyOCR is required for image files. "
                "Install with: pip install matchaudit[ocr]"
            )

    ocr_kwargs: dict[str, object] = {
        "language": [lang.strip() for lang in ocr_language.split(",")],
        "conf_threshold": ocr_conf_threshold,
        "ocr_upscale": ocr_upscale,
    }

    # -- Run comparisons ------------------------------------------------------
    results: list[tuple[str, ComparisonResult]] = []

    for stem, src_path, cap_path in pairs:
        try:
            source_reader = detect_reader(src_path)
            source_df = source_reader.read(src_path)

            if ocr_reader is not None and _is_image(cap_path):
                captured_df = ocr_reader.read(cap_path, **ocr_kwargs)
            else:
                captured_df = detect_reader(cap_path).read(cap_path)

            keys: list[str]
            if key_columns:
                keys = [k.strip() for k in key_columns.split(",")]
            else:
                detected = _auto_detect_key_columns(source_df, captured_df)
                if detected:
                    keys = detected
                else:
                    click.echo(f"⚠️  {stem}: no se pudo auto-detectar key column, se saltea")
                    continue

            result = run_comparison(source_df, captured_df, keys)
            results.append((stem, result))

        except Exception as exc:
            click.echo(f"❌  {stem}: error — {exc}")
            continue

    # -- Output ---------------------------------------------------------------
    _render_batch_summary(console, results)


@main.command()
def validate() -> None:
    """Validate a control point against source data."""
    click.echo("validate: not yet implemented")


# ── Batch helpers ────────────────────────────────────────────────────────────


def _find_batch_pairs(
    source_dir: Path, captured_dir: Path
) -> tuple[list[tuple[str, Path, Path]], set[str], set[str]]:
    """Scan *source_dir* and *captured_dir*, pair files by stem name.

    Returns:
        (pairs, unmatched_sources, unmatched_captures)
        where each pair is (stem, source_path, captured_path).
    """
    source_extensions = {".csv", ".xlsx", ".xls"}
    captured_extensions = source_extensions | {".png", ".jpg", ".jpeg"}

    sources: dict[str, Path] = {}
    for f in source_dir.iterdir():
        if f.is_file() and f.suffix.lower() in source_extensions:
            sources.setdefault(f.stem, f)

    captures: dict[str, Path] = {}
    for f in captured_dir.iterdir():
        if f.is_file() and f.suffix.lower() in captured_extensions:
            captures.setdefault(f.stem, f)

    common = set(sources) & set(captures)
    pairs = [(stem, sources[stem], captures[stem]) for stem in sorted(common)]
    unmatched_src = set(sources) - common
    unmatched_cap = set(captures) - common
    return pairs, unmatched_src, unmatched_cap


def _warn_unmatched(
    console: Console,
    side: str,
    stems: list[str],
    directory: Path,
) -> None:
    """Print a warning about files without a matching partner."""
    console.print(
        f"[yellow]⚠️  {len(stems)} archivo(s) en {directory.name} "
        f"(#{side}) no tienen contraparte:[/yellow]"
    )
    for name in stems:
        console.print(f"   {name}")


def _render_batch_summary(
    console: Console,
    results: list[tuple[str, ComparisonResult]],
) -> None:
    """Render a summary table for batch comparison results, then detail panels
    for each pair that has mismatches."""
    if not results:
        console.print("[yellow]No se produjeron resultados.[/yellow]")
        return

    from rich.table import Table

    # ── Summary table ────────────────────────────────────────────────────
    summary = Table(title="Resultado Consolidado — Comparación por Lote")
    summary.add_column("Archivo", style="bold")
    summary.add_column("Estado", no_wrap=True)
    summary.add_column("Match Rate")
    summary.add_column("Esperadas")
    summary.add_column("Capturadas")
    summary.add_column("Coinciden")
    summary.add_column("Diferencias")
    summary.add_column("Faltantes")
    summary.add_column("Sobrantes")

    ok_count = 0
    total_pairs = len(results)

    for stem, result in results:
        status = result.status
        emoji = "✅" if status == "match" else "❌"
        rate = f"{result.stats.match_rate:.1%}" if result.stats else "-"
        exp = str(result.stats.total_expected) if result.stats else "-"
        cap = str(result.stats.total_captured) if result.stats else "-"
        matched = str(result.matched_rows)
        diffs = str(len(result.mismatched_rows))
        missing = str(len(result.missing_rows))
        extra = str(len(result.extra_rows))

        summary.add_row(
            stem, f"{emoji} {status.upper()}", rate, exp, cap,
            matched, diffs, missing, extra,
        )

        if status == "match":
            ok_count += 1

    console.print(summary)
    console.print(
        f"\n[bold]{ok_count}/{total_pairs}[/bold] archivos OK, "
        f"[bold]{total_pairs - ok_count}[/bold] con diferencias\n"
    )

    # ── Detail panels for mismatches ─────────────────────────────────────
    for stem, result in results:
        if result.status == "match":
            continue
        console.rule(f"[red]{stem}[/red]")
        render_comparison(result)


if __name__ == "__main__":
    main()
