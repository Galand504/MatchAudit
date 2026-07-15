"""Smoke tests for the MatchAudit CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from matchaudit.cli import main

try:
    import easyocr  # noqa: F401

    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False


class TestMatchAuditCli:
    """Smoke tests verifying the CLI boots and responds."""

    def test_help_displays(self, cli_runner: CliRunner) -> None:
        """Running ``matchaudit --help`` exits successfully and shows help text."""
        result: Result = cli_runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "MatchAudit" in result.output

    def test_version_displays(self, cli_runner: CliRunner) -> None:
        """Running ``matchaudit --version`` shows the package version."""
        result: Result = cli_runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert result.output.strip()

    def test_validate_command_stubbed(self, cli_runner: CliRunner) -> None:
        """Running ``matchaudit validate`` shows a stub message."""
        result: Result = cli_runner.invoke(main, ["validate"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_compare_command_help_shows_flags(self, cli_runner: CliRunner) -> None:
        """Running ``matchaudit compare --help`` shows expected options."""
        result: Result = cli_runner.invoke(main, ["compare", "--help"])
        assert result.exit_code == 0
        assert "--source" in result.output
        assert "--captured" in result.output
        assert "--key-columns" in result.output
        assert "--output" in result.output
        assert "--ocr" in result.output
        assert "--ocr-language" in result.output
        assert "--ocr-conf-threshold" in result.output

    @pytest.mark.parametrize(
        ("args", "expected_exit"),
        [
            (["nonexistent"], 2),
            (["--unknown-flag"], 2),
        ],
    )
    def test_invalid_args_exit_with_error(
        self, cli_runner: CliRunner, args: list[str], expected_exit: int
    ) -> None:
        """Invalid commands or flags exit with code 2 (Click built-in)."""
        result: Result = cli_runner.invoke(main, args)
        assert result.exit_code == expected_exit

    def test_compare_ocr_flag_errors_without_easyocr(
        self, cli_runner: CliRunner, sample_csv: Path, sample_xlsx: Path
    ) -> None:
        """Running ``compare --ocr`` without easyocr shows installation hint."""
        result: Result = cli_runner.invoke(
            main,
            [
                "compare",
                "--source",
                str(sample_csv),
                "--captured",
                str(sample_xlsx),
                "--key-columns",
                "id",
                "--ocr",
            ],
        )
        if not HAS_EASYOCR:
            assert result.exit_code == 1
            assert "matchaudit[ocr]" in result.output
        else:
            # With easyocr installed it should try to read CSVs as images → error
            assert result.exit_code != 0
